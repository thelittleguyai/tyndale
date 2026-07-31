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
import datetime
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.attest import evaluate_attest_state
from app.agents.orchestrator import documents_all_satisfied, finalize_audit
from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.db.session import get_session
from app.schemas.api_contract import MultiUploadResponse, UploadedDoc, UploadResponse
from app.sources.document_classifier import classify_document
from app.sources.extraction import (  # OCR engine (CO-12A: moved out of ocr_tools)
    _grep_date,
    grep_patient_name,
    grep_provider_name,
    run_document_ocr,
)

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
def _classify(ocr_text: str, filename: str | None = None) -> tuple[str, float]:
    """Return (document_type, classification_confidence) via the layered classifier
    (Sprint E). Adds MSN / MA-EOB / Medicaid-MCO / GFE / TRICARE / VA / community-care
    types; an ambiguous document is 'unclassified', never guessed."""
    return classify_document(ocr_text, filename).as_tuple()


async def _persist(content: bytes, filename: str) -> str:
    """Write the upload to local disk or Azure Blob; return a URI/path string."""
    settings = get_settings()
    if settings.azure_storage_account_url:
        try:
            # Async client → async credential (the sync DefaultAzureCredential is not
            # awaitable and breaks the aio client). Both are async context managers, so
            # `async with` closes the credential's aiohttp session + the client cleanly.
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            async with DefaultAzureCredential() as cred, BlobServiceClient(
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


# HEIC/HEIF ISO-BMFF brands (bytes 8-12) we accept — iPhone photos are 'heic'/'mif1'.
_HEIF_BRANDS = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1", b"heif"}
)


def _sniff_upload_type(content: bytes) -> str | None:
    """Content-based (magic-byte) file type — the ONLY trustworthy signal (the client MIME/
    extension is user-controlled). Returns a short type name for a PDF or an Azure-DI-processable
    image, else None. Closes the security gap where any ≤20MB payload was stored + sent to OCR,
    and lets a non-document upload fail fast at the door with a readable 422 instead of dead-ending
    on a 0-item encounter screen."""
    if not content:
        return None
    if content[:4] == b"%PDF":
        return "pdf"
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if content[:2] == b"BM":
        return "bmp"
    if len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in _HEIF_BRANDS:
        return "heic"
    return None


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
    # Reject non-PDF/non-image payloads BEFORE storing or OCRing them (security + honesty): a
    # grocery-list .txt, a Word doc, an empty file, etc. can never become a bill, so fail fast with
    # a readable reason instead of persisting arbitrary bytes and dead-ending on a 0-item encounter.
    if _sniff_upload_type(content) is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{filename}' doesn't look like a PDF or image. Upload a PDF, or a clear photo "
                "(JPG, PNG, or HEIC) of your bill, EOB, insurance card, or plan summary."
            ),
        )
    uri = await _persist(content, filename)
    ocr = await run_document_ocr(
        {"content_base64": base64.b64encode(content).decode(), "filename": filename}
    )
    full_text = ocr.get("ocr_text") or ""
    document_type, confidence = _classify(full_text, filename)
    document_id = str(uuid.uuid4())
    entry: dict[str, Any] = {
        "document_id": document_id,
        "filename": filename,
        "uri": uri,
        "document_type": document_type,
        "classification_confidence": confidence,
        # Typed extraction at parse time (DL-39) — the Record row title/date read these, never
        # parsed-back-out-of prose. Conservative; None when no structured anchor is present.
        "provider_name": grep_provider_name(full_text),
        "patient_name": grep_patient_name(full_text),
        "date_of_service": _grep_date(full_text, ("DATE OF SERVICE", "SERVICE DATE", "DOS")),
        "byte_count": len(content),
        "ocr_text_preview": (ocr.get("ocr_text") or "")[:1000],
        # Full OCR text length (admin visibility): 0 chars alongside extraction_status='error'
        # is the tell that extraction degraded — so a stalled/degraded audit is diagnosable.
        "ocr_text_chars": len(ocr.get("ocr_text") or ""),
        # 'extracted' | 'error' — a real-OCR failure degrades here (empty text) instead of
        # crashing the request; the document is still persisted so nothing is lost.
        "extraction_status": ocr.get("extraction_status") or "extracted",
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
    background: BackgroundTasks,
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

    # Capture the pre-upload state BEFORE commit (async expire_on_commit would make these await-only
    # afterwards) — the trigger for re-running a needs_documents audit once the user has now
    # supplied every missing input.
    reaudit = (
        case is not None
        and case_file_id is not None
        and case.status == "audit_incomplete"
        and case.audit_incomplete_reason == "needs_documents"
    )
    if case is None:
        case = CaseFile(user_id=user.user_id, status="open", documents=documents)
        session.add(case)
    else:
        case.documents = documents  # reassign — SQLAlchemy doesn't track in-place JSONB mutation
    reaudit = reaudit and documents_all_satisfied(case)  # …all checklist items now satisfied

    # Promote the typed provider / date-of-service onto the case (first structured hit wins; a
    # re-upload never overwrites an already-known value). The Record row reads these typed fields.
    if case.provider_name is None:
        case.provider_name = next(
            (d.get("provider_name") for d in documents if isinstance(d, dict) and d.get("provider_name")),
            None,
        )
    if case.date_of_service is None:
        _dos = next(
            (d.get("date_of_service") for d in documents if isinstance(d, dict) and d.get("date_of_service")),
            None,
        )
        if _dos:
            try:
                case.date_of_service = datetime.date.fromisoformat(str(_dos)[:10])
            except ValueError:
                pass
    if case.patient_name is None:
        case.patient_name = next(
            (d.get("patient_name") for d in documents if isinstance(d, dict) and d.get("patient_name")),
            None,
        )
    # Attest-and-proceed trigger (§A2 state 1): extracted patient ≠ profile name flips the
    # case to attest_status='required' BEFORE encounter verification can proceed.
    _attest_user = (
        await session.execute(select(User).where(User.user_id == case.user_id))
    ).scalar_one_or_none()
    if _attest_user is not None:
        _was = case.attest_status
        if evaluate_attest_state(case, _attest_user) and _was != "required":
            from app.analytics.emit import emit as _emit

            await _emit(
                "attestation_required", user_id=case.user_id, case_file_id=case.case_file_id
            )
    await session.flush()
    cfid = str(case.case_file_id)
    await session.commit()

    # Internal analytics (P0): the upload funnel is server-known. Best-effort, own sessions.
    from app.analytics.emit import emit
    from app.analytics.events import coerce_enum

    cf_uuid = UUID(cfid)
    await emit("upload_started", user_id=user.user_id, case_file_id=cf_uuid,
               properties={"file_count": len(incoming)})
    await emit("documents_accepted", user_id=user.user_id, case_file_id=cf_uuid,
               properties={"doc_count": len(uploaded)})
    for d in uploaded:
        dt = coerce_enum("extraction_succeeded", "doc_type", d.document_type or "unclassified")
        await emit("extraction_succeeded", user_id=user.user_id, case_file_id=cf_uuid,
                   properties={"doc_type": dt})

    if reaudit:
        # All missing documents provided → re-run the audit (finalize_audit sets audit_running,
        # then a terminal status). The results screen the user returns to polls status.
        log.info("upload.needs_documents_satisfied_reaudit", case_file_id=cfid)
        # Close-the-loop (flagship metric): the case's needs_documents request is satisfied.
        # Idempotent per case so it pairs 1:1 with document_request_issued.
        from app.analytics.emit import emit_idempotent

        await emit_idempotent("document_request_satisfied",
                              dedupe_key=f"document_request_satisfied:{cfid}",
                              user_id=user.user_id, case_file_id=cf_uuid)
        background.add_task(finalize_audit, cfid)

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
    # Chat-first bootstrap (DL-91): a NEW case gets a thread (acknowledgment + live status card) and
    # the client routes there instead of the classic encounter screen. Flag-gated no-op (returns
    # None) — appended-to-existing uploads (case_file_id given) never bootstrap.
    conversation_id: str | None = None
    if case_file_id is None:
        from app.agents.thread_bridge import bootstrap_thread

        conversation_id = await bootstrap_thread(cfid)
    return MultiUploadResponse(
        case_file_id=cfid,
        uploads=uploaded,
        chat_first=conversation_id is not None,
        conversation_id=conversation_id,
    )
