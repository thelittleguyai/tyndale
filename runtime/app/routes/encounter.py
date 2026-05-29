"""Encounter-verification routes (Phase 2I).

The two-phase audit:
  POST /v1/audit/{id}/extract        -> Bill Detective translates line items
  GET  /v1/audit/{id}/line-items     -> idempotent fetch for the verification UI
  POST /v1/audit/{id}/confirmations  -> persist confirmations + kick finalize (bg)
  GET  /v1/audit/{id}/status         -> poll the case status

The existing GET /v1/audit/{id} (audit.py) stays the final-result fetch; the
mobile screen polls /status until 'audit_complete' before calling it.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.agents.orchestrator import (
    extract_line_items,
    finalize_audit,
    submit_confirmations,
)
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.schemas.encounter import (
    AuditStatusResponse,
    ConfirmationsAccepted,
    ConfirmationsRequest,
    ExtractResult,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


def _validate_uuid(case_file_id: str) -> None:
    try:
        UUID(case_file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="case_file_id must be a UUID") from None


@router.post("/audit/{case_file_id}/extract", response_model=ExtractResult)
async def extract(case_file_id: str) -> ExtractResult:
    _validate_uuid(case_file_id)
    return await extract_line_items(case_file_id)


@router.get("/audit/{case_file_id}/line-items", response_model=ExtractResult)
async def get_line_items(case_file_id: str) -> ExtractResult:
    """Idempotent fetch — re-projects whatever line items are persisted without
    re-running the translate pass."""
    _validate_uuid(case_file_id)
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(
            select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id))
        )).scalar_one_or_none()
    if cf is None:
        raise HTTPException(status_code=404, detail="case_file not found")
    if not cf.line_items:
        # Not extracted yet — run extraction now (idempotent).
        return await extract_line_items(case_file_id)
    from app.schemas.encounter import DEFAULT_INTRO_MESSAGE, LineItem

    return ExtractResult(
        case_file_id=case_file_id,
        status="encounter_verification_pending",
        line_items=[LineItem(**it) for it in cf.line_items],
        intro_message=DEFAULT_INTRO_MESSAGE,
    )


@router.post("/audit/{case_file_id}/confirmations", response_model=ConfirmationsAccepted)
async def post_confirmations(
    case_file_id: str,
    body: ConfirmationsRequest,
    background: BackgroundTasks,
) -> ConfirmationsAccepted:
    _validate_uuid(case_file_id)
    if not body.confirmations:
        raise HTTPException(status_code=400, detail="confirmations must be non-empty")
    accepted = await submit_confirmations(case_file_id, body.confirmations)
    # Kick the finalize audit asynchronously; the UI polls /status.
    background.add_task(finalize_audit, case_file_id)
    return accepted


@router.get("/audit/{case_file_id}/status", response_model=AuditStatusResponse)
async def get_status(case_file_id: str) -> AuditStatusResponse:
    _validate_uuid(case_file_id)
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(
            select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id))
        )).scalar_one_or_none()
    if cf is None:
        raise HTTPException(status_code=404, detail="case_file not found")
    return AuditStatusResponse(case_file_id=case_file_id, status=cf.status)
