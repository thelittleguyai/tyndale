"""Encounter-verification routes (Phase 2I).

The two-phase audit:
  POST /v1/audit/{id}/extract        -> Bill Detective translates line items
  GET  /v1/audit/{id}/line-items     -> idempotent fetch for the verification UI
  POST /v1/audit/{id}/confirmations  -> persist confirmations + kick finalize (bg)
  GET  /v1/audit/{id}/status         -> poll the case status

The existing GET /v1/audit/{id} (audit.py) stays the final-result fetch; the
mobile screen polls /status until 'audit_complete' before calling it.

All routes require an authenticated session and case ownership (security fix:
previously unauthenticated, exposing any case by UUID — IDOR).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import (
    extract_line_items,
    finalize_audit,
    submit_confirmations,
)
from app.auth import CurrentUser, current_user
from app.db.session import get_session
from app.routes.case_access import require_case_owner
from app.schemas.encounter import (
    AuditStatusResponse,
    ConfirmationsAccepted,
    ConfirmationsRequest,
    ExtractResult,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/audit/{case_file_id}/extract", response_model=ExtractResult)
async def extract(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ExtractResult:
    await require_case_owner(case_file_id, user, session)
    return await extract_line_items(case_file_id)


@router.get("/audit/{case_file_id}/line-items", response_model=ExtractResult)
async def get_line_items(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ExtractResult:
    """Idempotent fetch — re-projects whatever line items are persisted without
    re-running the translate pass."""
    cf = await require_case_owner(case_file_id, user, session)
    if not cf.line_items:
        # Not extracted yet — run extraction now (idempotent).
        return await extract_line_items(case_file_id)
    from app.agents.example_scenarios import backfill_scenarios
    from app.schemas.encounter import DEFAULT_INTRO_MESSAGE, LineItem

    # Phase 2L: backfill example scenarios for rows persisted before 2L.
    items = backfill_scenarios([dict(it) for it in cf.line_items])
    return ExtractResult(
        case_file_id=case_file_id,
        status="encounter_verification_pending",
        line_items=[LineItem(**it) for it in items],
        intro_message=DEFAULT_INTRO_MESSAGE,
    )


@router.post("/audit/{case_file_id}/confirmations", response_model=ConfirmationsAccepted)
async def post_confirmations(
    case_file_id: str,
    body: ConfirmationsRequest,
    background: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ConfirmationsAccepted:
    await require_case_owner(case_file_id, user, session)
    if not body.confirmations:
        raise HTTPException(status_code=400, detail="confirmations must be non-empty")
    accepted = await submit_confirmations(case_file_id, body.confirmations)
    # Kick the finalize audit asynchronously; the UI polls /status.
    background.add_task(finalize_audit, case_file_id)
    return accepted


@router.get("/audit/{case_file_id}/status", response_model=AuditStatusResponse)
async def get_status(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AuditStatusResponse:
    cf = await require_case_owner(case_file_id, user, session)
    return AuditStatusResponse(case_file_id=case_file_id, status=cf.status)
