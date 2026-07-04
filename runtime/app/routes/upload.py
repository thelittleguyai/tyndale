"""POST /v1/upload — multi-document upload (Phase 2L).

Accepts N files in one multipart request (bill + EOB + insurance card + plan
summary, per the acceptance narrative "Maya uploads four crumpled photos"),
persists + classifies each, and attaches them all to one case file — a new case,
or an existing one via case_file_id.

Backwards compat (14-day window per the phase prompt): the old singular shape
(file=...) is still accepted and returns the legacy single-file response; a
deprecation warning is logged.

Storage / classification stay the walking-skeleton approach (Azure Blob or local
/tmp; keyword OCR classify with a heuristic confidence). Per-file + total request
size are bounded by Phase 2K.2 (per-file here, total request in the size-limit
middleware).
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.session import get_session
from app.schemas.api_contract import MultiUploadResponse, UploadedDoc, UploadResponse
from app.sources.extraction import run_document_ocr  # OCR engine (CO-12A: moved out of ocr_tools)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


# The benefits document goes by a dozen names — recognize them ALL as the
# plan_summary type (CO-12C). Human-readable list (surfaced to the UI) + the
# uppercase match markers. Acronyms are matched parenthesized "(SBC)" to avoid
# false-positiving a bare "SBC"/"EOC" substring inside a bill.
BENEFITS_DOC_ALIASES: tuple[str, ...] = (
    "Summary of Benefits and Coverage (SBC)",
    "Schedule of Benefits",
    "Summary Plan Description (SPD)",
    "Benefit Summary / Plan Summary",
    "Certificate of Coverage (COC)",
    "Evidence of Coverage (EOC)",
    "Outline of Coverage",
    "Member Benefit Booklet / Benefit Booklet / Member Handbook",
    "Plan Document",
    "Coverage Summary",
    "Benefits at a Glance",
)
_BENEFITS_DOC_MARKERS: tuple[str, ...] = (
    "SUMMARY OF BENEFITS",
    "SCHEDULE OF BENEFITS",
    "SUMMARY PLAN DESCRIPTION",
    "BENEFIT SUMMARY",
    "PLAN SUMMARY",
    "CERTIFICATE OF COVERAGE",
    "EVIDENCE OF COVERAGE",
    "OUTLINE OF COVERAGE",
    "BENEFIT BOOKLET",
    "MEMBER HANDBOOK",
    "PLAN DOCUMENT",
    "COVERAGE SUMMARY",
    "BENEFITS AT A GLANCE",
    "CERTIFICATE OF INSURANCE",
    "(SBC)",
    "(SPD)",
    "(COC)",
    "(EOC)",
)


def _classify(ocr_text: str) -> tuple[str, float]:
    """Return (document_type, classification_confidence). Walking-skeleton keyword
    scan; Phase 2H/4 replaces with the upload_classify_document tool + a real model."""
    t = ocr_text.upper()
    if "EXPLANATION OF BENEFITS" in t or "EOB" in t or "MEMBER RESPONSIBILITY" in t:
        return "eob", 0.9
    if "MEMBER ID" in t or "GROUP NUMBER" in t or "RX BIN" in t:
        return "insurance_card", 0.9
    if any(m in t for m in _BENEFITS_DOC_MARKERS):
        return "plan_summary", 0.85
    if "ADVERSE BENEFIT DETERMINATION" in t or "DENIAL" in t or "DENIED" in t or "NOT COVERED" in t:
        return "denial_letter", 0.8
    if "COLLECTION" in t or "PAST DUE" in t or "FINAL NOTICE" in t or "DELINQUENT" in t:
        return "collections_notice", 0.8
    if "AMOUNT DUE" in t or "BILLED" in t or "STATEMENT" in t or "CPT" in t:
        return "bill", 0.85
    return "other", 0.4


async def _persist(content: bytes, filename: str) -> str:
    """Write the upload to local disk or Azure Blob; return a URI/path string."""
    settings = get_settings()
    if settings.azure_storage_account_url:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            cred = DefaultAzureCredential()
            async with BlobServiceClient(
                account_url=settings.azure_storage_account_url, credential=cred
            ) as svc:
                container = svc.get_container_client(settings.azure_storage_uploads_container)
                blob_name = f"{uuid.uuid4()}_{filename}"
                await container.upload_blob(name=blob_name, data=content, overwrite=False)
                return f"{settings.azure_storage_account_url}/{settings.azure_storage_uploads_container}/{blob_name}"
        except Exception as exc:  # noqa: BLE001 — Blob is the durable store; never downgrade
            # PHI must land durably in Azure Blob (BAA-covered, DL-47). Never silently fall
            # back to the replica's EPHEMERAL local disk when Blob is the configured store —
            # that loses PHI on restart and puts it on non-durable, off-BAA storage. Fail clean.
            log.error(
                "upload.blob_failed",
                error_class=type(exc).__name__,
                container=settings.azure_storage_uploads_container,
                exc_info=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Upload storage is temporarily unavailable — please try again in a moment.",
            ) from exc

    # No Azure Blob configured → local disk. Acceptable ONLY in local dev; NEVER in
    # production (an ephemeral upload store in prod means PHI loss + off-BAA storage).
    if settings.is_production:
        log.error("upload.no_durable_storage_in_prod")
        raise HTTPException(
            status_code=503,
            detail="Upload storage is not available — please try again later.",
        )
    target_dir = Path(settings.local_uploads_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{filename or 'upload'}"
    path = target_dir / safe_name
    path.write_bytes(content)
    return str(path)


async def _process_one(content: bytes, filename: str) -> tuple[dict[str, Any], UploadedDoc]:
    """Persist + classify one file. Returns (case-file document entry, API doc)."""
    settings = get_settings()
    if len(content) > settings.max_upload_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"'{filename}' exceeds the {settings.max_upload_file_bytes}-byte per-file limit. "
                "Upload a smaller file — V1-Lite does not support chunked upload."
            ),
        )
    uri = await _persist(content, filename)
    ocr = await run_document_ocr(
        {"content_base64": base64.b64encode(content).decode(), "filename": filename}
    )
    document_type, confidence = _classify(ocr.get("ocr_text") or "")
    document_id = str(uuid.uuid4())
    entry: dict[str, Any] = {
        "document_id": document_id,
        "filename": filename,
        "uri": uri,
        "document_type": document_type,
        "classification_confidence": confidence,
        "byte_count": len(content),
        "ocr_text_preview": (ocr.get("ocr_text") or "")[:1000],
    }
    api_doc = UploadedDoc(
        document_id=document_id,
        filename=filename,
        document_type=document_type,
        classification_confidence=confidence,
        size_bytes=len(content),
    )
    return entry, api_doc


@router.post("/upload")
async def upload(
    files: list[UploadFile] = File(default=[]),
    file: UploadFile | None = File(default=None),  # deprecated singular form (14-day compat)
    case_file_id: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
):
    # Backwards compat: the old single-file shape (file=...). Returns the legacy
    # response so in-flight clients don't break.
    singular = file is not None and not files
    incoming = [file] if singular else list(files)
    if not incoming:
        raise HTTPException(status_code=400, detail="no files provided")
    if singular:
        log.warning("upload.deprecated_singular_file_form", note="use files=[...] (Phase 2L)")

    # Attach to an existing case, or open a new one.
    case: CaseFile | None = None
    if case_file_id:
        try:
            cf_uuid = UUID(case_file_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="case_file_id must be a UUID") from None
        case = (
            await session.execute(select(CaseFile).where(CaseFile.case_file_id == cf_uuid))
        ).scalar_one_or_none()
        # 404 covers both not-found and not-owned (anti-enumeration).
        if case is None or case.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="case_file not found")

    documents: list[dict[str, Any]] = list(case.documents) if case else []
    uploaded: list[UploadedDoc] = []
    for f in incoming:
        content = await f.read()
        entry, api_doc = await _process_one(content, f.filename or "upload")
        documents.append(entry)
        uploaded.append(api_doc)

    if case is None:
        case = CaseFile(user_id=user.user_id, status="open", documents=documents)
        session.add(case)
    else:
        case.documents = documents  # reassign — SQLAlchemy doesn't track in-place JSONB mutation
    await session.flush()
    cfid = str(case.case_file_id)
    await session.commit()

    log.info(
        "upload.processed",
        case_file_id=cfid,
        file_count=len(uploaded),
        document_types=[d.document_type for d in uploaded],
        attached_to_existing=case_file_id is not None,
    )

    if singular:
        first = uploaded[0]
        return UploadResponse(
            case_file_id=cfid,
            document_id=first.document_id,
            filename=first.filename,
            received_bytes=first.size_bytes,
            note=f"document_type={first.document_type}",
        )
    return MultiUploadResponse(case_file_id=cfid, uploads=uploaded)
