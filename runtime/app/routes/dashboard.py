"""GET /v1/dashboard — single composite payload that powers the signed-in
dashboard.

Shape lives in app/schemas/dashboard.py and packages/shared/src/dashboard.ts
(mirror each other one-for-one). Combines: brief user info, the most recent
coverage extraction, amount-saved-YTD, open cases, and the lead-with-status
greeting (Change Order 001 item 3) when there are open cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.greeting import compose_status_greeting
from app.auth import CurrentUser, current_user
from app.crons.outcome_followup import scan_for_outcome_followups
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.findings import Finding
from app.db.session import get_session
from app.schemas.dashboard import (
    CopayAmount,
    CoverageCopays,
    CoverageMeter,
    CoverageSummary,
    DashboardPayload,
    OpenCase,
    UserBrief,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


# --- Coverage projection -----------------------------------------------------
def _coverage_meter(d: dict | None, key_total: str, key_met: str) -> CoverageMeter | None:
    if not d:
        return None
    total = d.get(key_total)
    met = d.get(key_met)
    if total is None or met is None:
        return None
    try:
        total = float(total)
        met = float(met)
    except (TypeError, ValueError):
        return None
    return CoverageMeter(total=total, met=met, remaining=max(0.0, total - met))


def _coverage_summary_from_jsonb(coverage_jsonb: dict | None) -> CoverageSummary:
    """Project the case_files.coverage JSONB into the dashboard's shape.

    The upload tools write coverage with the FHIR-shape fields
    (deductible_amount, deductible_met, oop_max_amount, oop_max_met,
    copay_pcp / copay_er / copay_specialist). Walking-skeleton handling.
    """
    if not coverage_jsonb:
        return CoverageSummary(extraction_status="missing")

    deductible = _coverage_meter(coverage_jsonb, "deductible_amount", "deductible_met")
    oop_max = _coverage_meter(coverage_jsonb, "oop_max_amount", "oop_max_met")

    copays = None
    pcp = coverage_jsonb.get("copay_pcp")
    er = coverage_jsonb.get("copay_er")
    spec = coverage_jsonb.get("copay_specialist")
    if pcp is not None or er is not None or spec is not None:
        copays = CoverageCopays(
            pcp_visit=CopayAmount(amount=float(pcp or 0)),
            er_visit=CopayAmount(amount=float(er or 0)),
            specialist=CopayAmount(amount=float(spec or 0)),
        )

    extracted = bool(deductible or oop_max or copays)
    status: Any = "extracted" if extracted else ("pending" if coverage_jsonb else "missing")
    return CoverageSummary(
        deductible=deductible,
        oop_max=oop_max,
        copays=copays,
        extraction_status=status,
    )


def _most_recent_coverage_jsonb(cases: list[CaseFile]) -> dict | None:
    """Return the coverage JSONB from the most recently updated case that has one."""
    for case in sorted(cases, key=lambda c: c.updated_at or c.created_at, reverse=True):
        if case.coverage:
            return case.coverage
    return None


def _intake_state(cases: list[CaseFile]) -> tuple[str, str | None]:
    """Drive the intake gate (Phase CO-1A) — a USER-LEVEL, one-time onboarding, NOT per case.

    No cases yet → ('not_started', 'welcome') routes a brand-new user into the wizard. A user
    who has EVER completed intake reads 'complete' forever: a newly created case (a fresh
    upload defaults to intake_status='not_started') must never shadow a completed intake and
    trap a returning user in the wizard — the 2026-07-06 regression, where the old
    most-recent-case derivation re-gated returning users the moment they started a new case.
    Otherwise (no completed case yet) resume the most recent case's wizard step.
    """
    if not cases:
        return "not_started", "welcome"
    if any((c.intake_status or "") == "complete" for c in cases):
        return "complete", "complete"
    case = max(cases, key=lambda c: c.created_at or datetime.now(timezone.utc))
    status = case.intake_status or "not_started"
    step = case.intake_current_step or ("welcome" if status != "complete" else None)
    return status, step


# --- Open cases / deadlines / amount-saved ----------------------------------
async def _open_cases_payload(
    s: AsyncSession, user_id: str, cases: list[CaseFile]
) -> list[OpenCase]:
    """Build the OpenCase list for cases in {open, in_progress}, with headline
    derived from the most recent finding's category, and the next pending
    deadline (if any) attached."""
    out: list[OpenCase] = []
    for case in cases:
        if case.status not in ("open", "in_progress", "extraction_failed"):
            continue

        # A degraded extraction is an open, actionable issue — surface it honestly so the user
        # knows to re-upload, and never silently drop it off the dashboard.
        if case.status == "extraction_failed":
            anchor = case.created_at or datetime.now(timezone.utc)
            out.append(
                OpenCase(
                    case_file_id=str(case.case_file_id),
                    headline="We couldn't read your documents — try re-uploading a clearer copy",
                    days_open=max(0, (datetime.now(timezone.utc) - anchor).days),
                    next_deadline_date=None,
                    next_deadline_label=None,
                )
            )
            continue

        # Headline — first prefer the most recent finding's category;
        # fall back to a doc-driven label.
        findings = (
            (
                await s.execute(
                    select(Finding)
                    .where(Finding.case_file_id == case.case_file_id)
                    .order_by(Finding.created_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .all()
        )
        if findings:
            f = findings[0]
            headline = (
                f"{f.category.replace('_', ' ').capitalize()} ({f.finding_type.replace('_', '-')})"
            )
        elif case.documents:
            first_doc = (
                case.documents[0] if isinstance(case.documents, list) and case.documents else {}
            )
            doc_type = (first_doc or {}).get("document_type") or "document"
            headline = f"Uploaded {doc_type} — audit pending"
        else:
            headline = "Case open — awaiting documents"

        # Days open
        anchor = case.created_at or datetime.now(timezone.utc)
        days_open = max(0, (datetime.now(timezone.utc) - anchor).days)

        # Next pending deadline
        deadline_rows = (
            (
                await s.execute(
                    select(Deadline)
                    .where(Deadline.case_file_id == case.case_file_id)
                    .where(Deadline.status == "pending")
                    .order_by(Deadline.deadline_date.asc())
                    .limit(1)
                )
            )
            .scalars()
            .all()
        )
        d = deadline_rows[0] if deadline_rows else None

        out.append(
            OpenCase(
                case_file_id=str(case.case_file_id),
                headline=headline,
                days_open=days_open,
                next_deadline_date=d.deadline_date if d else None,
                next_deadline_label=(d.description if d else None),
            )
        )
    return out


async def _amount_saved_ytd(s: AsyncSession, cases: list[CaseFile]) -> float:
    """Sum of payer-side gaps surfaced this year — the V1-Lite proxy for
    'amount saved'. Real reconciliation against confirmed-settlement events
    lands when feedback loop ingestion does (Phase 4)."""
    if not cases:
        return 0.0
    year = datetime.now(timezone.utc).year
    case_ids = [c.case_file_id for c in cases]
    rows = (
        (
            await s.execute(
                select(Finding)
                .where(Finding.case_file_id.in_(case_ids))
                .where(Finding.finding_type == "payer_side")
            )
        )
        .scalars()
        .all()
    )
    total = 0.0
    for f in rows:
        if f.created_at and f.created_at.year != year:
            continue
        gap = (f.facts or {}).get("gap")
        try:
            if gap is not None:
                total += float(gap)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


# --- Route -------------------------------------------------------------------
@router.get("/dashboard", response_model=DashboardPayload)
async def get_dashboard(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardPayload:
    # Load all the user's cases once.
    cases = (
        (await session.execute(select(CaseFile).where(CaseFile.user_id == user.user_id)))
        .scalars()
        .all()
    )

    coverage_summary = _coverage_summary_from_jsonb(_most_recent_coverage_jsonb(cases))
    intake_status, intake_current_step = _intake_state(cases)
    open_cases = await _open_cases_payload(session, str(user.user_id), cases)
    amount_saved = await _amount_saved_ytd(session, cases)

    greeting = await compose_status_greeting([oc.model_dump(mode="json") for oc in open_cases])

    # Phase 2J — inline the outcome follow-up prompts so the dashboard gets
    # them in one round trip.
    followups = await scan_for_outcome_followups(user_id=str(user.user_id))
    outcome_prompts = [
        {
            "case_file_id": f.case_file_id,
            "days_since_recommendation": f.days_since_recommendation,
            "finding_summary": f.finding_summary,
        }
        for f in followups
    ]

    return DashboardPayload(
        user=UserBrief(id=str(user.user_id), first_name=user.first_name),
        coverage=coverage_summary,
        amount_saved_ytd=amount_saved,
        intake_status=intake_status,
        intake_current_step=intake_current_step,
        has_cases=len(cases) > 0,
        open_cases=open_cases,
        outcome_prompts=outcome_prompts,
        status_forward_greeting=greeting,
    )
