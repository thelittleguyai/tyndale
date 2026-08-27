"""GET /v1/dashboard — single composite payload that powers the signed-in
dashboard.

Shape lives in app/schemas/dashboard.py and packages/shared/src/dashboard.ts
(mirror each other one-for-one). Combines: brief user info, the most recent
coverage extraction, amount-saved-YTD, open cases, and the lead-with-status
greeting (Change Order 001 item 3) when there are open cases.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_loader import orchestration_step
from app.agents.greeting import compose_status_greeting
from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.users import User
from app.crons.outcome_followup import scan_for_outcome_followups
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.findings import Finding
from app.db.session import get_session
from app.schemas.case_file import as_dict
from app.schemas.dashboard import (
    ActiveCase,
    HomeBanner,
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

# Full-lifecycle status -> (user-facing label, which screen resumes it). 'resolved'/'archived'
# are terminal and intentionally absent (they don't appear on the Open Cases card). The audit
# results screen would poll forever on a pre-encounter case, so pre-audit statuses resume at the
# encounter screen and the audit lifecycle resumes at the results screen.
_ACTIVE_CASE_STATUS: dict[str, tuple[str, str]] = {
    "open": ("Ready to review", "encounter"),
    "in_progress": ("Ready to review", "encounter"),
    "extraction_failed": ("We couldn't read your documents", "encounter"),
    "not_a_bill": ("This isn't a medical bill", "encounter"),
    "encounter_verification_pending": ("Verify your visit", "encounter"),
    "encounter_verified": ("Audit starting", "results"),
    "awaiting_eob_confirmation": ("Confirm your EOBs", "results"),
    "audit_running": ("Audit running", "results"),
    "audit_complete": ("Results ready", "results"),
    "audit_incomplete": ("Audit incomplete", "results"),
}


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

    # Benefit-bar source labels (mockups, honest subset): "entries" when any contributing
    # value is user-attested (checklist saves carry user-entered provenance), else
    # "documents" (SBC / card extraction). Meters only ever read STATED values — a prior
    # can never become a bar.
    prov = coverage_jsonb.get("user_input_provenance") or {}

    def _source(*keys: str) -> str:
        return "entries" if any(
            (prov.get(k) or {}).get("source") == "user-entered" for k in keys
        ) else "documents"

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
        deductible_source=_source("deductible_amount", "deductible_met") if deductible else None,
        oop_max_source=_source("oop_max_amount", "oop_max_met") if oop_max else None,
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
                    headline=orchestration_step("dashboard.headline_unreadable"),
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
            headline = orchestration_step(
                "dashboard.headline_finding",
                category_label=f.category.replace("_", " ").capitalize(),
                finding_type_label=f.finding_type.replace("_", "-"),
            )
        elif case.documents:
            first_doc = (
                case.documents[0] if isinstance(case.documents, list) and case.documents else {}
            )
            doc_type = (first_doc or {}).get("document_type") or "document"
            headline = orchestration_step("dashboard.headline_uploaded", doc_type=doc_type)
        else:
            headline = orchestration_step("dashboard.headline_open")

        # Days open
        anchor = case.created_at or datetime.now(timezone.utc)
        days_open = max(0, (datetime.now(timezone.utc) - anchor).days)

        # Next pending deadline
        d = await _next_pending_deadline(s, case.case_file_id)

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


async def _next_pending_deadline(s: AsyncSession, case_id) -> Deadline | None:
    """The soonest still-pending deadline for a case, or None."""
    return (
        (
            await s.execute(
                select(Deadline)
                .where(Deadline.case_file_id == case_id)
                .where(Deadline.status == "pending")
                .order_by(Deadline.deadline_date.asc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def _active_cases_payload(s: AsyncSession, cases: list[CaseFile]) -> list[ActiveCase]:
    """Status-aware, full-lifecycle resumable cases for the Open Cases card. Every case whose
    status is in _ACTIVE_CASE_STATUS (i.e. not resolved/archived) gets a card with a plain-
    language status and the screen that resumes it. Ordered most-recently-created first so the
    case a user is actively working sits on top."""
    out: list[ActiveCase] = []
    for case in sorted(cases, key=lambda c: c.created_at or datetime.min, reverse=True):
        mapped = _ACTIVE_CASE_STATUS.get(case.status)
        if mapped is None:
            continue  # terminal (resolved/archived) or unknown — not a resumable card
        label, resume = mapped
        # HP-1: a document-blocked audit reads as an action, not a failure, on the dashboard too.
        if case.status == "audit_incomplete" and case.audit_incomplete_reason == "needs_documents":
            label = "Needs your documents"
        anchor = case.created_at or datetime.now(timezone.utc)
        d = await _next_pending_deadline(s, case.case_file_id)
        out.append(
            ActiveCase(
                case_file_id=str(case.case_file_id),
                status=case.status,
                label=label,
                resume=resume,
                days_open=max(0, (datetime.now(timezone.utc) - anchor).days),
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
        gap = (as_dict(f.facts) or {}).get("gap")
        try:
            if gap is not None:
                total += float(gap)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


# Statuses genuinely blocked on the USER — the banner's "N need(s) something from you" and
# the stat card's "needs you" count both derive from this one set (no new states).
_NEEDS_YOU_STATUSES = {
    "encounter_verification_pending", "awaiting_eob_confirmation",
    "extraction_failed", "not_a_bill",
}


def _needs_you(case: CaseFile) -> bool:
    if case.status in _NEEDS_YOU_STATUSES:
        return True
    return case.status == "audit_incomplete" and case.audit_incomplete_reason == "needs_documents"


def _compose_banner(name: str, cases: list[CaseFile]) -> dict:
    """Registry-authored banner from REAL state only (honest subset of Brock's mockup — the
    proactive-monitoring line is B8, unbuilt, and test-banned from this surface)."""
    from app.agents.context_loader import orchestration_step

    open_cases = [c for c in cases if c.status not in ("resolved", "archived")]
    n_open, n_needs = len(open_cases), sum(1 for c in open_cases if _needs_you(c))
    title = orchestration_step("home.banner_title", name=name)
    if n_open == 0:
        subline = orchestration_step("home.banner_subline_empty")
    else:
        cases_phrase = f"{n_open} open case{'' if n_open == 1 else 's'}"
        if n_needs:
            needs_phrase = (
                f"{n_needs} need{'s' if n_needs == 1 else ''} something from you"
            )
            subline = orchestration_step(
                "home.banner_subline_active",
                cases_phrase=cases_phrase, needs_phrase=needs_phrase,
            )
        else:
            subline = orchestration_step(
                "home.banner_subline_quiet", cases_phrase=cases_phrase
            )
    return {"title": title, "subline": subline}


# --- Route -------------------------------------------------------------------
def _welcome_state_hash(case_states: list[dict]) -> str:
    """Stable hash of the case-state snapshot the welcome summary is composed from — status +
    deadline per case, order-independent. The summary regenerates only when this changes."""
    # Stringify every element so a None/date/str mix sorts without a TypeError.
    snap = sorted(
        (str(s.get("status")), str(s.get("next_deadline_date")), str(s.get("next_deadline_label")))
        for s in case_states
    )
    return hashlib.sha256(json.dumps(snap).encode()).hexdigest()


async def _cached_welcome_summary(
    session: AsyncSession, user_id, case_states: list[dict]
) -> str | None:
    """Return the welcome summary, reusing the persisted one while the case-state hash is unchanged
    and regenerating (+ re-storing) only when it changes — same words every load until state moves."""
    state_hash = _welcome_state_hash(case_states)
    urow = (
        await session.execute(select(User).where(User.user_id == user_id))
    ).scalar_one_or_none()
    cache = (urow.welcome_summary_cache if urow else None) or {}
    if cache.get("hash") == state_hash:
        return cache.get("summary")
    summary = await compose_status_greeting(case_states)
    if urow is not None:
        urow.welcome_summary_cache = {"hash": state_hash, "summary": summary}
        await session.commit()
    return summary


@router.get("/dashboard", response_model=DashboardPayload)
async def get_dashboard(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardPayload:
    # Load all the user's cases once (excluding ones the user has removed).
    cases = (
        (
            await session.execute(
                select(CaseFile)
                .where(CaseFile.user_id == user.user_id)
                .where(CaseFile.soft_deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )

    coverage_summary = _coverage_summary_from_jsonb(_most_recent_coverage_jsonb(cases))
    intake_status, intake_current_step = _intake_state(cases)
    open_cases = await _open_cases_payload(session, str(user.user_id), cases)
    active_cases = await _active_cases_payload(session, cases)
    amount_saved = await _amount_saved_ytd(session, cases)

    # Welcome summary — composed from every case's state (not just open ones) so the count
    # breakdown reflects results + needs-docs too; cached on a hash of that snapshot.
    _dl = {ac.case_file_id: (ac.next_deadline_date, ac.next_deadline_label) for ac in active_cases}
    case_states = [
        {
            "status": c.status,
            "next_deadline_date": _dl.get(str(c.case_file_id), (None, None))[0],
            "next_deadline_label": _dl.get(str(c.case_file_id), (None, None))[1],
        }
        for c in cases
    ]
    greeting = await _cached_welcome_summary(session, user.user_id, case_states)

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

    # Stat cards (mockups item 3): CONFIRMED recovered only (outcome reports — never the
    # payer-gap proxy), and the open/needs-you counts from the same set the banner uses.
    from app.sources.record import confirmed_recovered_by_case

    recovered_map = await confirmed_recovered_by_case(
        session, [c.case_file_id for c in cases], user.user_id
    )
    recovered_to_date = round(sum(recovered_map.values()), 2)
    open_cases_all = [c for c in cases if c.status not in ("resolved", "archived")]
    needs_you_count = sum(1 for c in open_cases_all if _needs_you(c))

    # Banner name: the profile's REAL first name when set (CO-17), else the email-derived one.
    urow = (
        await session.execute(select(User).where(User.user_id == user.user_id))
    ).scalar_one_or_none()
    banner_name = ((urow.first_name or "").strip() if urow else "") or user.first_name or "there"

    return DashboardPayload(
        user=UserBrief(id=str(user.user_id), first_name=user.first_name),
        banner=HomeBanner(**_compose_banner(banner_name, cases)),
        recovered_to_date=recovered_to_date,
        open_count=len(open_cases_all),
        needs_you_count=needs_you_count,
        coverage=coverage_summary,
        amount_saved_ytd=amount_saved,
        intake_status=intake_status,
        intake_current_step=intake_current_step,
        has_cases=len(cases) > 0,
        open_cases=open_cases,
        active_cases=active_cases,
        outcome_prompts=outcome_prompts,
        status_forward_greeting=greeting,
        record_enabled=get_settings().enable_record_view,
        coverage_connection_enabled=bool(get_settings().enable_coverage_connection),
    )
