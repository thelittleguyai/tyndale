"""POST /v1/audit — returns the MRI scenario fixture (stub)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api_contract import AuditRequest
from app.schemas.case_file import AuditResult
from app.stubs.fixtures import mri_audit_fixture

router = APIRouter(tags=["v1"])


@router.post("/audit", response_model=AuditResult)
async def audit(req: AuditRequest) -> AuditResult:
    # Phase 1C: no real Claude orchestration; return the MRI three-number fixture.
    return mri_audit_fixture(req.case_file_id)
