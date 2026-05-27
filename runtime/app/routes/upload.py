"""POST /v1/upload — accepts a multipart file; does not persist content yet (stub)."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, UploadFile

from app.schemas.api_contract import UploadResponse
from app.stubs.fixtures import MRI_CASE_FILE_ID

router = APIRouter(tags=["v1"])


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    # Phase 1C: we read the bytes to report size but do NOT persist file content
    # or run OCR (USE_REAL_OCR is off; real ingestion lands in Phase 2).
    return UploadResponse(
        case_file_id=MRI_CASE_FILE_ID,
        document_id=str(uuid4()),
        filename=file.filename or "upload",
        received_bytes=len(content),
    )
