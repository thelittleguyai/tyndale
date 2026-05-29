"""POST /v1/audit — runs the real Bill Detective + Math Person + Lead Planner
sequence and returns the AuditResult (three-number audit + findings + composed
markdown).

Falls back to the MRI fixture when USE_REAL_CLAUDE is off (or when the
Anthropic key is missing and allow_fixture_fallback is true) — that path
short-circuits inside ``orchestrator.run_audit``.

GET /v1/audit/{case_file_id} returns the current persisted state (idempotent
fetch — useful for the mobile app's polling pattern while the audit runs).
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException

from app.agents.orchestrator import _assemble_result, run_audit
from app.schemas.api_contract import AuditRequest
from app.schemas.case_file import AuditResult

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/audit", response_model=AuditResult)
async def post_audit(req: AuditRequest) -> AuditResult:
    try:
        UUID(req.case_file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="case_file_id must be a UUID") from None
    return await run_audit(req.case_file_id)


@router.get("/audit/{case_file_id}", response_model=AuditResult)
async def get_audit(case_file_id: str) -> AuditResult:
    try:
        UUID(case_file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="case_file_id must be a UUID") from None
    # Idempotent fetch: read the persisted findings and project to AuditResult.
    return await _assemble_result(case_file_id, composed="")
