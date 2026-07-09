"""GET /v1/cases — list of the authenticated user's case files."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.db.session import get_session
from app.routes.case_access import require_case_owner
from app.schemas.dashboard import CaseSummary, CasesListPayload
from app.security.audit_writer import build_audit_event

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
            .where(CaseFile.soft_deleted_at.is_(None))  # hide user-removed cases
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


# Statuses that carry a real audit result (in flight or complete) — never user-removable.
_NON_REMOVABLE_STATUSES = {"audit_running", "audit_complete", "resolved"}


@router.delete("/cases/{case_file_id}", status_code=204)
async def remove_case(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Member-initiated soft-delete of a junk / mistaken case — for the dashboard's "remove this
    case" affordance. Ownership-checked (404 anti-enumeration), audited, and reversible in the DB
    (the row is retained, just hidden from every user-scoped list). A case with findings or a
    running/complete audit is protected (409): the user must never silently drop real results."""
    case = await require_case_owner(case_file_id, user, session)
    if case.soft_deleted_at is not None:
        return Response(status_code=204)  # idempotent — already removed
    findings_count = (
        await session.execute(
            select(func.count())
            .select_from(Finding)
            .where(Finding.case_file_id == case.case_file_id)
        )
    ).scalar_one()
    if case.status in _NON_REMOVABLE_STATUSES or findings_count > 0:
        raise HTTPException(
            status_code=409,
            detail="This case has results, so it can't be removed here.",
        )
    now = datetime.now(timezone.utc)
    case.soft_deleted_at = now
    case.soft_deleted_by = user.user_id
    case.updated_at = now
    session.add(
        build_audit_event(
            event_type="user_action",
            actor=str(user.user_id),
            user_id=user.user_id,
            case_file_id=case.case_file_id,
            payload={"action": "remove_case", "prior_status": case.status},
            outcome="success",
        )
    )
    await session.commit()
    log.info("case.soft_delete", case_file_id=str(case.case_file_id), user_id=str(user.user_id))
    return Response(status_code=204)
