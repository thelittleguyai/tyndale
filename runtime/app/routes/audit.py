"""POST /v1/audit — runs the real Bill Detective + Math Person + Lead Planner
sequence and returns the AuditResult (three-number audit + findings + composed
markdown).

Falls back to the MRI fixture when USE_REAL_CLAUDE is off (or when the
Anthropic key is missing and allow_fixture_fallback is true) — that path
short-circuits inside ``orchestrator.run_audit``.

GET /v1/audit/{case_file_id} returns the current persisted state (idempotent
fetch — useful for the mobile app's polling pattern while the audit runs).

Both routes require an authenticated session and case ownership (security
fix: previously unauthenticated, exposing any case by UUID — IDOR).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import _assemble_result, run_audit
from app.auth import CurrentUser, current_user
from app.db.session import get_session
from app.routes.case_access import require_case_owner
from app.schemas.api_contract import AuditRequest
from app.schemas.case_file import AuditResult

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/audit", response_model=AuditResult)
async def post_audit(
    req: AuditRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AuditResult:
    await require_case_owner(req.case_file_id, user, session)
    return await run_audit(req.case_file_id)


@router.get("/audit/{case_file_id}", response_model=AuditResult)
async def get_audit(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AuditResult:
    await require_case_owner(case_file_id, user, session)
    # Idempotent fetch: read the persisted findings and project to AuditResult.
    return await _assemble_result(case_file_id, composed="")
