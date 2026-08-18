"""Plan documents — the plan-level SBC home (2026-08-19, settings item 5).

An SBC describes the user's PLAN, not one bill. Before this, the only way to give
Tyndale your benefits summary was to attach it to a case — and every OTHER case kept
asking for it. This surface uploads it once at the user level; the needs/unlock-more
resolvers count it for every case, and its extracted terms feed rung-2 when a case
has no coverage of its own.

Reuses the existing document path end-to-end: the same magic-byte gate, size cap,
OCR engine, classifier, and SBC term extraction as case uploads; the same
BlobStorage serve pattern as insurance cards (signed URL on Azure, streamed bytes
locally). An upload that classifies OFF the SBC family is stored (the user chose to
file it here) but never silently counted as the plan summary — the response says
what it looked like.
"""

from __future__ import annotations

import base64
import re
import uuid as uuid_mod
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import documents_all_satisfied, finalize_audit
from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.models.plan_documents import PlanDocument
from app.db.session import get_session
from app.ingestion.blob_storage import BlobStorage
from app.ingestion.extract_documents import extract_sbc_from_text
from app.routes.upload import _sniff_upload_type
from app.sources.document_classifier import classify_document
from app.sources.extraction import run_document_ocr
from app.sources.plan_docs import SBC_FAMILY

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

_MIME_BY_SNIFF = {
    "pdf": "application/pdf",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    "heic": "image/heic",
}


def _plan_storage() -> BlobStorage:
    # Plan documents are PHI-bearing files → the uploads container, like card images.
    return BlobStorage(container=get_settings().azure_storage_uploads_container)


def _blob_path(user_id: UUID, plan_document_id: str, filename: str) -> str:
    # PHI-free key: ids + a sanitized filename tail (no member data in the path).
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[-80:] or "document"
    return f"plan-docs/{user_id}/{plan_document_id}_{safe}"


class PlanDocumentOut(BaseModel):
    plan_document_id: str
    document_type: str
    filename: str
    uploaded_at: str
    # True when SBC term extraction read at least one plan term — the UI can say
    # "terms read" vs "stored, but I couldn't read the numbers".
    has_coverage_terms: bool = False
    is_sbc: bool = False


class PlanDocumentsPayload(BaseModel):
    documents: list[PlanDocumentOut]
    # The checklist-satisfying fact, precomputed for the client.
    sbc_on_file: bool = False


def _out(row: PlanDocument) -> PlanDocumentOut:
    return PlanDocumentOut(
        plan_document_id=str(row.plan_document_id),
        document_type=row.document_type,
        filename=row.filename,
        uploaded_at=row.uploaded_at.isoformat() if row.uploaded_at else "",
        has_coverage_terms=bool(row.coverage),
        is_sbc=row.document_type in SBC_FAMILY,
    )


@router.get("/plan/documents", response_model=PlanDocumentsPayload)
async def list_plan_documents(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> PlanDocumentsPayload:
    rows = (
        (
            await session.execute(
                select(PlanDocument)
                .where(PlanDocument.user_id == user.user_id)
                .order_by(PlanDocument.uploaded_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return PlanDocumentsPayload(
        documents=[_out(r) for r in rows],
        sbc_on_file=any(r.document_type in SBC_FAMILY for r in rows),
    )


@router.post("/plan/documents", response_model=PlanDocumentOut)
async def upload_plan_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> PlanDocumentOut:
    settings = get_settings()
    content = await file.read()
    filename = file.filename or "plan-document"
    if len(content) > settings.max_upload_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"'{filename}' exceeds the {settings.max_upload_file_bytes}-byte per-file limit.",
        )
    sniffed = _sniff_upload_type(content)
    if sniffed is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{filename}' doesn't look like a PDF or image. Upload your Summary of "
                "Benefits and Coverage as a PDF or a clear photo."
            ),
        )

    ocr = await run_document_ocr(
        {"content_base64": base64.b64encode(content).decode(), "filename": filename}
    )
    full_text = ocr.get("ocr_text") or ""
    document_type, _confidence = classify_document(full_text, filename).as_tuple()
    coverage = extract_sbc_from_text(full_text).high_confidence_coverage()

    plan_document_id = str(uuid_mod.uuid4())
    blob_ref = _blob_path(user.user_id, plan_document_id, filename)
    await _plan_storage().write_bytes(blob_ref, content)

    row = PlanDocument(
        plan_document_id=UUID(plan_document_id),
        user_id=user.user_id,
        document_type=document_type,
        filename=filename,
        blob_ref=blob_ref,
        mime_type=_MIME_BY_SNIFF.get(sniffed),
        file_size=len(content),
        coverage=coverage or None,
        ocr_text_chars=len(full_text),
        extraction_status=ocr.get("extraction_status") or "extracted",
    )
    session.add(row)

    # A plan-level SBC can be the LAST missing input on a stalled case — honor the same
    # close-the-loop promise as a case upload: re-run every needs_documents case this
    # upload completes. Captured before commit (expire_on_commit).
    reaudit_ids: list[str] = []
    if document_type in SBC_FAMILY:
        stalled = (
            (
                await session.execute(
                    select(CaseFile).where(
                        CaseFile.user_id == user.user_id,
                        CaseFile.status == "audit_incomplete",
                        CaseFile.audit_incomplete_reason == "needs_documents",
                    )
                )
            )
            .scalars()
            .all()
        )
        reaudit_ids = [
            str(c.case_file_id) for c in stalled if documents_all_satisfied(c, plan_sbc=True)
        ]
    await session.commit()

    from app.analytics.emit import emit_idempotent

    for cfid in reaudit_ids:
        log.info("plan_documents.needs_documents_satisfied_reaudit", case_file_id=cfid)
        await emit_idempotent(
            "document_request_satisfied",
            dedupe_key=f"document_request_satisfied:{cfid}",
            user_id=user.user_id,
            case_file_id=UUID(cfid),
        )
        background.add_task(finalize_audit, cfid)

    log.info(
        "plan_documents.uploaded",
        plan_document_id=plan_document_id,
        document_type=document_type,
        has_coverage_terms=bool(coverage),
        reaudits=len(reaudit_ids),
    )
    return _out(row)


@router.get("/plan/documents/{plan_document_id}/file")
async def get_plan_document_file(
    plan_document_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
):
    row = await _owned_row(session, user, plan_document_id)
    storage = _plan_storage()
    url = storage.signed_url(row.blob_ref, minutes=15)
    if url:
        # Azure: short-lived, PHI-free signed Blob URL (same pattern as card images).
        return RedirectResponse(url)
    data = await storage.read_bytes(row.blob_ref)
    return Response(content=data, media_type=row.mime_type or "application/octet-stream")


@router.delete("/plan/documents/{plan_document_id}", status_code=204)
async def delete_plan_document(
    plan_document_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    row = await _owned_row(session, user, plan_document_id)
    try:
        await _plan_storage().delete(row.blob_ref)
    except Exception:  # noqa: BLE001 — the DB row is the source of truth; a blob orphan is loggable
        log.warning("plan_documents.blob_delete_failed", plan_document_id=plan_document_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)


async def _owned_row(
    session: AsyncSession, user: CurrentUser, plan_document_id: str
) -> PlanDocument:
    try:
        pd_uuid = UUID(plan_document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="plan document not found") from None
    row = (
        await session.execute(
            select(PlanDocument).where(PlanDocument.plan_document_id == pd_uuid)
        )
    ).scalar_one_or_none()
    # 404 covers not-found and not-owned alike (anti-enumeration).
    if row is None or row.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="plan document not found")
    return row
