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

from app.agents.context_loader import orchestration_step
from app.agents.orchestrator import _documents_needed
from app.appeals.deadlines import DEADLINE_RULES
from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.findings import Finding
from app.db.session import get_session
from app.routes.case_access import require_case_owner
from app.schemas.case_summary import (
    CaseSummaryPayload,
    FindingBrief,
    StatusBanner,
)
from app.schemas.record import (
    DeadlineInfo,
    RecordAggregates,
    RecordPayload,
    SubCaseRow,
    ThreeNumberBrief,
)
from app.sources.call_identifiers import of_case
from app.sources.gameplan import build_gameplan, humanize_category
from app.sources.record import (
    confirmed_recovered_by_case,
    deadlines_for_case,
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


# ONE source of truth for a row's displayed state: BOTH the chip and the second line derive from
# it, so they can never disagree (a computed three-number line under a "Verify visit" chip was the
# bug). The three-number line shows ONLY in the 'results' state.
_STATE_BY_STATUS: dict[str, str] = {
    "audit_complete": "results",
    "resolved": "results",
    "audit_incomplete": "needs_documents",
    "awaiting_eob_confirmation": "needs_documents",
    "extraction_failed": "unreadable",
    "not_a_bill": "not_a_bill",
    "audit_running": "auditing",
    "encounter_verified": "auditing",
    "encounter_verification_pending": "verifying",
    "archived": "results",
}


def _row_state(status: str) -> str:
    return _STATE_BY_STATUS.get(status, "in_progress")


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
        state = _row_state(c.status)
        nci = next_check_in_date(c, fs)
        rows.append(
            SubCaseRow(
                case_file_id=cid,
                provider=_row_provider(c),
                service_date=_row_service_date(c),
                status=c.status,
                state=state,
                label=label,
                resume=resume,
                # Gate the three-number line to the results state so it never appears under a
                # non-results chip (the chip + line derive from the same _row_state).
                three_number=ThreeNumberBrief(**tn) if (tn and state == "results") else None,
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


# States where the case is legitimately blocked on the user providing more documents — the only
# states the have/need checklist should surface (a complete audit has no open document items).
_NEEDS_DOCS_STATES = {"audit_incomplete", "awaiting_eob_confirmation"}


def _first(values, *keys) -> str | None:
    """First non-empty string at any of `keys` across a JSONB list of dicts (best-effort, honest:
    returns None rather than inventing a value when the structured field isn't present)."""
    for v in values or []:
        if isinstance(v, dict):
            for k in keys:
                got = v.get(k)
                if isinstance(got, str) and got.strip():
                    return got.strip()
    return None


# Proper-cased document-type labels for the fallback title — acronyms stay uppercase (EOB not
# "Eob"), never a raw-enum capitalize(). Unknown types get a sentence-cased humanization.
_DOC_TYPE_LABELS: dict[str, str] = {
    "eob": "EOB",
    "msn": "MSN",
    "ma_eob": "MA EOB",
    "gfe": "GFE",
    "sbc": "SBC",
    "itemized_bill": "Itemized bill",
    "bill": "Bill",
    "insurance_card": "Insurance card",
    "denial_letter": "Denial letter",
    "collections_notice": "Collections notice",
    "mco_notice": "Medicaid notice",
}


def _doc_type_label(dt: str) -> str:
    return _DOC_TYPE_LABELS.get(dt, dt.replace("_", " ").capitalize())


def _row_provider(case) -> str | None:
    """The Record row TITLE — the provider, not the status (the status is the trailing chip).
    Fallback chain: the TYPED provider_name (persisted at extraction) → any provider name in the
    structured EOB/document artifacts → the primary document's classified type as a '<type> visit'
    (properly cased) → None (the client renders a neutral 'Bill review')."""
    if getattr(case, "provider_name", None):
        return case.provider_name
    name = _first(case.eobs, "provider", "provider_name") or _first(
        case.documents, "provider", "provider_name"
    )
    if name:
        return name
    for d in case.documents or []:
        if isinstance(d, dict):
            dt = d.get("document_type")
            if isinstance(dt, str) and dt and dt != "unclassified":
                return f"{_doc_type_label(dt)} visit"
    return None


def _row_service_date(case) -> str | None:
    """Date of service — the TYPED date_of_service if persisted, else the structured EOB/document
    field. NOT the upload date. None when not extracted."""
    typed = getattr(case, "date_of_service", None)
    if typed is not None:
        return typed.isoformat() if hasattr(typed, "isoformat") else str(typed)
    return _first(case.eobs, "date_of_service", "service_date") or _first(
        case.documents, "date_of_service", "service_date"
    )


def _finding_brief(f: Finding) -> FindingBrief:
    facts = f.facts or {}
    gap = facts.get("gap")
    try:
        dollar = round(max(0.0, float(gap)), 2) if gap is not None else None
    except (TypeError, ValueError):
        dollar = None
    claim = (f.legal_claim or {}).get("claim")
    action = (f.recommendation or {}).get("action")
    return FindingBrief(
        finding_id=str(f.finding_id),
        finding_type=f.finding_type,
        category=f.category,
        title=humanize_category(f.category),
        claim=claim.strip() if isinstance(claim, str) and claim.strip() else None,
        dollar_impact=dollar,
        recommendation=action.strip() if isinstance(action, str) and action.strip() else None,
    )


@router.get("/case/{case_file_id}/summary", response_model=CaseSummaryPayload)
async def get_case_summary(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CaseSummaryPayload:
    """The permanent sub-case summary (D5 §2). Hidden (404) when ENABLE_RECORD_VIEW is off, so the
    Record feature ships as one gated unit. Ownership-checked (IDOR); a soft-deleted case 404s."""
    if not get_settings().enable_record_view:
        raise HTTPException(status_code=404, detail="not found")
    case = await require_case_owner(case_file_id, user, session)
    if case.soft_deleted_at is not None:
        raise HTTPException(status_code=404, detail="case_file not found")

    findings = (
        await session.execute(
            select(Finding).where(Finding.case_file_id == case.case_file_id)
        )
    ).scalars().all()

    label, _resume = _label_and_resume(case.status)
    deadlines = await deadlines_for_case(session, case.case_file_id)
    recovered = await confirmed_recovered_by_case(session, [case.case_file_id])

    tn = three_number_from_findings(findings)
    open_items = _documents_needed(case) if case.status in _NEEDS_DOCS_STATES else []
    # Typed call identifiers (B4) off the case's own columns — populated at parse time by newer
    # uploads and by the one-shot backfill for older cases. Null fields simply don't render.
    call_ids = of_case(case)

    return CaseSummaryPayload(
        case_file_id=str(case.case_file_id),
        status_banner=StatusBanner(
            status=case.status,
            label=label,
            response_deadline=DeadlineInfo(**deadlines[0]) if deadlines else None,
        ),
        provider=_first(case.eobs, "provider", "provider_name")
        or _first(case.documents, "provider", "provider_name"),
        service_date=_first(case.eobs, "date_of_service")
        or _first(case.documents, "date_of_service", "service_date"),
        three_number=ThreeNumberBrief(**tn) if tn else None,
        identified_estimate=identified_estimate_from_findings(findings),
        recovered_so_far=recovered.get(str(case.case_file_id), 0.0),
        findings=[_finding_brief(f) for f in findings],
        open_items=open_items,
        next_check_in_date=(
            d.isoformat() if (d := next_check_in_date(case, findings)) else None
        ),
        claim_number=call_ids.claim_number,
        account_number=call_ids.account_number,
        gameplan=build_gameplan(findings, call_ids),
        call_mode_intro=orchestration_step("call_mode_intro"),
        call_mode_outro=orchestration_step("call_mode_outro"),
    )
