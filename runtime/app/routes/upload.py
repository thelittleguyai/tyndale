"""POST /v1/upload — persists the file, opens a case file, runs quick OCR
classification, returns case_file_id + document_id + document_type.

Walking skeleton storage:
  * If azure_storage_account_url is set → upload to Azure Blob ``uploads`` container.
  * Otherwise → write to ``settings.local_uploads_dir`` (default /tmp/tyndale_uploads).

Walking skeleton classification:
  * Runs Azure Document Intelligence (or stub if USE_REAL_OCR=false) on the
    bytes and classifies as 'bill' | 'eob' | 'insurance_card' | 'other' by
    simple keyword scan on the OCR text. Phase 2H replaces this with the
    upload_classify_document tool + encounter-verification UI confirmation.
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.session import get_session
from app.schemas.api_contract import UploadResponse
from app.tools.ocr_tools import _bill_ocr_extract  # the registered fn

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


def _classify(ocr_text: str) -> str:
    t = ocr_text.upper()
    if "EXPLANATION OF BENEFITS" in t or "EOB" in t or "MEMBER RESPONSIBILITY" in t:
        return "eob"
    if "MEMBER ID" in t or "GROUP NUMBER" in t or "RX BIN" in t:
        return "insurance_card"
    if "AMOUNT DUE" in t or "BILLED" in t or "STATEMENT" in t or "CPT" in t:
        return "bill"
    return "other"


async def _persist(content: bytes, filename: str) -> str:
    """Write the upload to local disk or Azure Blob; return a URI/path string."""
    settings = get_settings()
    if settings.azure_storage_account_url:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            cred = DefaultAzureCredential()
            async with BlobServiceClient(account_url=settings.azure_storage_account_url, credential=cred) as svc:
                container = svc.get_container_client(settings.azure_storage_uploads_container)
                blob_name = f"{uuid.uuid4()}_{filename}"
                await container.upload_blob(name=blob_name, data=content, overwrite=False)
                return f"{settings.azure_storage_account_url}/{settings.azure_storage_uploads_container}/{blob_name}"
        except Exception as exc:  # noqa: BLE001 — fall back to local for walking skeleton
            log.warning("upload.blob_failed_falling_back_local", error=str(exc))

    target_dir = Path(settings.local_uploads_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{filename or 'upload'}"
    path = target_dir / safe_name
    path.write_bytes(content)
    return str(path)


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> UploadResponse:
    content = await file.read()
    # Per-file size limit (Phase 2K.2 / DL-46). The request-size middleware caps
    # the whole multipart body; this caps the individual file. V1-Lite has no
    # chunked upload — a smaller file is the only recourse.
    settings = get_settings()
    if len(content) > settings.max_upload_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds the {settings.max_upload_file_bytes}-byte per-file limit. "
                "Upload a smaller file."
            ),
        )
    filename = file.filename or "upload"

    # Persist + classify
    uri = await _persist(content, filename)
    ocr = await _bill_ocr_extract({"content_base64": base64.b64encode(content).decode(), "filename": filename})
    document_type = _classify(ocr.get("ocr_text") or "")

    # Open a case + record the document. user.user_id comes from the dev
    # auth stub today; Phase 2K swaps it for the real JWT subject.
    user_id = user.user_id
    document_id = str(uuid.uuid4())
    doc_entry: dict[str, Any] = {
        "document_id": document_id,
        "filename": filename,
        "uri": uri,
        "document_type": document_type,
        "byte_count": len(content),
        "ocr_text_preview": (ocr.get("ocr_text") or "")[:1000],
    }

    case = CaseFile(
        user_id=user_id,
        status="open",
        documents=[doc_entry],
    )
    session.add(case)
    await session.flush()
    case_file_id = str(case.case_file_id)
    await session.commit()

    log.info(
        "upload.created_case",
        case_file_id=case_file_id,
        document_id=document_id,
        document_type=document_type,
        filename=filename,
        byte_count=len(content),
    )
    return UploadResponse(
        case_file_id=case_file_id,
        document_id=document_id,
        filename=filename,
        received_bytes=len(content),
        note=f"document_type={document_type}",
    )
