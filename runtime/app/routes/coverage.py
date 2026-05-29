"""GET /v1/coverage — most recent coverage extraction in full detail.

In Phase 2H the dashboard uses the embedded summary inside /v1/dashboard,
so this route is "ready but not bound" — the case-detail screens consume
it in a later phase.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.case_files import CaseFile
from app.db.session import get_session
from app.routes.dashboard import _coverage_summary_from_jsonb, _most_recent_coverage_jsonb
from app.schemas.dashboard import CoverageDetailPayload

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.get("/coverage", response_model=CoverageDetailPayload)
async def get_coverage(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CoverageDetailPayload:
    cases = (
        await session.execute(select(CaseFile).where(CaseFile.user_id == user.user_id))
    ).scalars().all()
    raw = _most_recent_coverage_jsonb(cases)
    summary = _coverage_summary_from_jsonb(raw)
    source_doc_ids: list[str] = []
    if raw and isinstance(raw, dict):
        source_doc_ids = list(raw.get("source_document_ids", []) or [])
    confidence = (raw or {}).get("coverage_terms_confidence", {}) or {}
    return CoverageDetailPayload(
        coverage=summary,
        source_document_ids=source_doc_ids,
        confidence=confidence if isinstance(confidence, dict) else {},
    )
