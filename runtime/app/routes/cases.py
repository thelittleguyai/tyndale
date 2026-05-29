"""GET /v1/cases — list of the authenticated user's case files."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.case_files import CaseFile
from app.db.session import get_session
from app.schemas.dashboard import CaseSummary, CasesListPayload

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


def _headline_for(case: CaseFile) -> str:
    """Cheap, deterministic headline for the cases list."""
    if case.documents and isinstance(case.documents, list) and case.documents:
        first = case.documents[0] or {}
        doc_type = first.get("document_type") or "document"
        return f"Uploaded {doc_type}"
    return "Case open"


@router.get("/cases", response_model=CasesListPayload)
async def list_cases(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CasesListPayload:
    rows = (
        await session.execute(
            select(CaseFile)
            .where(CaseFile.user_id == user.user_id)
            .order_by(CaseFile.updated_at.desc())
        )
    ).scalars().all()
    summaries = [
        CaseSummary(
            case_file_id=str(c.case_file_id),
            headline=_headline_for(c),
            status=c.status,
            last_updated=(c.updated_at or c.created_at or datetime.now(timezone.utc)).isoformat(),
        )
        for c in rows
    ]
    return CasesListPayload(cases=summaries)
