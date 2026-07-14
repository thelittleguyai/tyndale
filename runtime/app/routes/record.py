"""GET /v1/record — the Tyndale Record (D5, Phase C). A rolling-window master view over a user's
sub-cases (case_files) + honest Record-level aggregates. Hidden (404) when ENABLE_RECORD_VIEW is
off. Data-honesty rules live in app/sources/record.py."""

from __future__ import annotations

import datetime
from collections import defaultdict

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appeals.deadlines import DEADLINE_RULES
from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.findings import Finding
from app.db.session import get_session
from app.schemas.record import (
    DeadlineInfo,
    RecordAggregates,
    RecordPayload,
    SubCaseRow,
    ThreeNumberBrief,
)
from app.sources.record import (
    confirmed_recovered_by_case,
    identified_estimate_from_findings,
    next_check_in_date,
    open_item_count,
    three_number_from_findings,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

# A sub-case with a fetchable summary (results-bearing) routes to /case/{id}; anything in flight
# routes to its thread. Terminal-failure states still have a summary (the honest needs-docs/failed
# view), so they're results-bearing here.
_RESULTS_BEARING = {
    "audit_complete", "audit_incomplete", "extraction_failed", "not_a_bill", "resolved", "archived",
}


def _label_and_resume(status: str) -> tuple[str, str]:
    from app.routes.dashboard import _ACTIVE_CASE_STATUS

    label = _ACTIVE_CASE_STATUS.get(status, ("In progress", "results"))[0]
    return label, ("summary" if status in _RESULTS_BEARING else "thread")


@router.get("/record", response_model=RecordPayload)
async def get_record(
    window_months: int = Query(default=12, ge=1, le=60),
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RecordPayload:
    if not get_settings().enable_record_view:
        raise HTTPException(status_code=404, detail="not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=window_months * 31)
    all_cases = (
        await session.execute(
            select(CaseFile)
            .where(CaseFile.user_id == user.user_id)
            .where(CaseFile.soft_deleted_at.is_(None))
            .order_by(CaseFile.created_at.desc())
        )
    ).scalars().all()
    in_window = [c for c in all_cases if c.created_at and c.created_at >= cutoff]
    has_older = len(in_window) < len(all_cases)
    case_ids = [c.case_file_id for c in in_window]

    # Batch the per-case reads (findings, deadlines, confirmed recoveries) to avoid N+1.
    findings_by_case: dict[str, list[Finding]] = defaultdict(list)
    deadline_by_case: dict[str, dict] = {}
    if case_ids:
        for f in (
            await session.execute(select(Finding).where(Finding.case_file_id.in_(case_ids)))
        ).scalars().all():
            findings_by_case[str(f.case_file_id)].append(f)
        for d in (
            await session.execute(
                select(Deadline)
                .where(Deadline.case_file_id.in_(case_ids))
                .where(Deadline.status == "pending")
                .order_by(Deadline.deadline_date)
            )
        ).scalars().all():
            key = str(d.case_file_id)
            if key not in deadline_by_case:  # earliest pending (ordered)
                rule = DEADLINE_RULES.get(d.deadline_type)
                deadline_by_case[key] = {
                    "label": rule.label if rule else (d.description or d.deadline_type),
                    "due_date": d.deadline_date.isoformat() if d.deadline_date else None,
                    "source": rule.source if rule else d.deadline_type,
                }
    recovered = await confirmed_recovered_by_case(session, case_ids)

    rows: list[SubCaseRow] = []
    total_billed = total_recovered = total_identified = 0.0
    open_items = 0
    checkins: list[datetime.date] = []
    for c in in_window:
        cid = str(c.case_file_id)
        fs = findings_by_case.get(cid, [])
        tn = three_number_from_findings(fs)
        oic = open_item_count(fs)
        rec = recovered.get(cid, 0.0)
        label, resume = _label_and_resume(c.status)
        nci = next_check_in_date(c, fs)
        rows.append(
            SubCaseRow(
                case_file_id=cid,
                status=c.status,
                label=label,
                resume=resume,
                three_number=ThreeNumberBrief(**tn) if tn else None,
                open_item_count=oic,
                next_deadline=DeadlineInfo(**deadline_by_case[cid]) if cid in deadline_by_case else None,
                recovered_so_far=rec,
            )
        )
        if tn:
            total_billed += tn["provider_billed"]
        total_recovered += rec
        total_identified += identified_estimate_from_findings(fs)
        open_items += oic
        if nci:
            checkins.append(nci)

    return RecordPayload(
        window_months=window_months,
        sub_cases=rows,
        aggregates=RecordAggregates(
            total_billed_reviewed=round(total_billed, 2),
            total_recovered=round(total_recovered, 2),
            total_identified=round(total_identified, 2),
            open_items=open_items,
            next_check_in_date=min(checkins).isoformat() if checkins else None,
        ),
        has_older=has_older,
    )
