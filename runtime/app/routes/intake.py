"""Guided intake wizard routes (Phase CO-1A).

A hand-holding, step-by-step intake that is the SOLE source of the user's benefits
state (DL-52 — no Stedi). Every captured field lands in the EXISTING
case_files.coverage JSONB / visit_context column — no parallel intake schema.

Endpoints:
  GET  /v1/intake/state                               — resume point + captured/missing
  POST /v1/intake/step/{step}/manual-entry            — persist a step's typed fields
  POST /v1/intake/step/{step}/skip                    — advance, persist nothing
  POST /v1/intake/step/insurance-card/extract         — OCR a card, return low-conf confirmations
  POST /v1/intake/visit-context                       — store the free-text "what were you seen for"
  POST /v1/intake/complete                            — validate + mark complete, return summary

All operate on the user's active case file (get-or-create); callers may pass an
explicit case_file_id (the wizard threads the one returned by /state).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.case_files import CaseFile
from app.db.models.plan_library import PlanLibraryEntry
from app.db.session import get_session
from app.ingestion.extract_documents import extract_insurance_card
from app.schemas.intake import (
    INTAKE_STEPS,
    CapturedData,
    CompletionSummary,
    ExtractRequest,
    IntakeStateResponse,
    PlanProposal,
    StepAck,
    VisitContextRequest,
)
from app.services import plan_library as plan_lib

router = APIRouter(tags=["v1"])

# Incoming manual-entry field name -> canonical case_files.coverage JSONB key.
_COVERAGE_ALIASES: dict[str, str] = {
    "deductible_total": "deductible_amount",
    "deductible_amount": "deductible_amount",
    "deductible_met": "deductible_met",
    "deductible_out_of_network": "deductible_out_of_network",
    "oop_max_total": "oop_max_amount",
    "oop_max_amount": "oop_max_amount",
    "oop_max_met": "oop_max_met",
    "oop_max_out_of_network": "oop_max_out_of_network",
    "coinsurance_percent": "coinsurance_percent",
    "coinsurance": "coinsurance_percent",
    "copay_pcp": "copay_pcp",
    "copay_specialist": "copay_specialist",
    "copay_er": "copay_er",
    "copay_urgent_care": "copay_urgent_care",
    "pcp_required": "pcp_required",
    "prior_auth_required": "prior_auth_required",
    "payer": "payer_name",
    "payer_name": "payer_name",
    "plan_name": "plan_name",
    "member_id": "member_id",
    "group_number": "group_number",
}

_COVERAGE_SIGNAL_KEYS = (
    "member_id",
    "payer_name",
    "plan_name",
    "deductible_amount",
    "oop_max_amount",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as e:
        raise HTTPException(status_code=422, detail="invalid case_file_id") from e


def _next_step(step: str) -> str:
    idx = INTAKE_STEPS.index(step)
    return INTAKE_STEPS[min(idx + 1, len(INTAKE_STEPS) - 1)]


def _current_step(case: CaseFile) -> str:
    return case.intake_current_step or INTAKE_STEPS[0]


def _completed_steps(case: CaseFile) -> list[str]:
    return INTAKE_STEPS[: INTAKE_STEPS.index(_current_step(case))]


def _doc_count(case: CaseFile, dtype: str) -> int:
    return sum(1 for d in (case.documents or []) if d.get("document_type") == dtype)


def _bills_count(case: CaseFile) -> int:
    return _doc_count(case, "bill")


def _eobs_count(case: CaseFile) -> int:
    return _doc_count(case, "eob") + len(case.eobs or [])


def _has_coverage(case: CaseFile) -> bool:
    cov = case.coverage or {}
    return any(cov.get(k) is not None for k in _COVERAGE_SIGNAL_KEYS)


def _missing_items(case: CaseFile) -> list[str]:
    cov = case.coverage or {}
    out: list[str] = []
    if cov.get("deductible_amount") is None:
        out.append("your plan's benefits (deductible / SBC)")
    elif cov.get("deductible_met") is None:
        out.append("how much of your deductible you've met this year")
    if cov.get("oop_max_amount") is None:
        out.append("your out-of-pocket maximum")
    if not (cov.get("member_id") or cov.get("payer_name")):
        out.append("your insurance plan details")
    if _bills_count(case) == 0:
        out.append("at least one medical bill")
    if _eobs_count(case) == 0:
        out.append("your EOB (your insurer's Explanation of Benefits)")
    if not case.visit_context:
        out.append("a short description of what your visit was for")
    return out


def _captured_data(case: CaseFile) -> CapturedData:
    return CapturedData(
        coverage=dict(case.coverage or {}),
        bills_count=_bills_count(case),
        eobs_count=_eobs_count(case),
        visit_context=case.visit_context,
    )


def _state(case: CaseFile) -> IntakeStateResponse:
    return IntakeStateResponse(
        case_file_id=str(case.case_file_id),
        intake_status=case.intake_status,
        current_step=_current_step(case),
        completed_steps=_completed_steps(case),
        captured_data=_captured_data(case),
        missing_items=_missing_items(case),
    )


def _ack(case: CaseFile, confirmations: list[dict] | None = None) -> StepAck:
    return StepAck(
        case_file_id=str(case.case_file_id),
        intake_status=case.intake_status,
        current_step=_current_step(case),
        completed_steps=_completed_steps(case),
        confirmations=confirmations or [],
    )


def _advance(case: CaseFile, from_step: str) -> None:
    case.intake_current_step = _next_step(from_step)
    if case.intake_status != "complete":
        case.intake_status = "in_progress"


async def _resolve_case(
    session: AsyncSession,
    user: CurrentUser,
    case_file_id: str | None,
    *,
    create: bool = False,
) -> CaseFile:
    if case_file_id:
        cf = (
            await session.execute(
                select(CaseFile).where(CaseFile.case_file_id == _uuid(case_file_id))
            )
        ).scalar_one_or_none()
        if cf is None or cf.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="case_file not found")
        return cf
    cf = (
        await session.execute(
            select(CaseFile)
            .where(CaseFile.user_id == user.user_id)
            .order_by(CaseFile.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if cf is None and create:
        cf = CaseFile(
            user_id=user.user_id,
            status="open",
            intake_status="not_started",
            intake_current_step=INTAKE_STEPS[0],
        )
        session.add(cf)
        await session.flush()
    if cf is None:
        raise HTTPException(status_code=404, detail="no case file for user")
    return cf


# --------------------------------------------------------------------------- #
# PlanLibrary propose-confirm (CO-12C)
# --------------------------------------------------------------------------- #
def _plan_year(case: CaseFile) -> int:
    """Plan year for PlanLibrary matching: coverage.plan_year, else the year of
    plan_effective_date, else the current calendar year."""
    cov = case.coverage or {}
    if cov.get("plan_year"):
        try:
            return int(cov["plan_year"])
        except (ValueError, TypeError):
            pass
    eff = cov.get("plan_effective_date")
    if eff:
        try:
            return int(str(eff)[:4])
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc).year


async def _pending_proposal(session: AsyncSession, case: CaseFile) -> PlanProposal | None:
    """A PlanLibrary proposal to surface before prompting for an SBC: the plan is
    identified (payer known) but the benefit design isn't captured and none is
    confirmed yet. None otherwise (the upload/manual path takes over)."""
    cov = case.coverage or {}
    if case.plan_current or cov.get("deductible_amount") is not None:
        return None
    payer = cov.get("payer_name")
    if not payer:
        return None
    entry = await plan_lib.match(session, payer, None, cov.get("plan_name"), _plan_year(case))
    return PlanProposal(**plan_lib.propose(entry)) if entry is not None else None


async def _load_plan_entry(session: AsyncSession, plan_library_id: Any) -> PlanLibraryEntry | None:
    if not plan_library_id:
        return None
    try:
        pid = uuid.UUID(str(plan_library_id))
    except (ValueError, TypeError):
        return None
    return (
        await session.execute(
            select(PlanLibraryEntry).where(PlanLibraryEntry.plan_library_id == pid)
        )
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/intake/state", response_model=IntakeStateResponse)
async def get_intake_state(
    case_file_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> IntakeStateResponse:
    """Resume point + what's captured/missing. Creates the user's first case file
    (intake_status='not_started') if they have none — the new-user entry point.
    Surfaces a PlanLibrary proposal (CO-12C) when the plan is identified but its
    benefit design isn't captured yet — the propose-confirm rescue path."""
    case = await _resolve_case(session, user, case_file_id, create=True)
    proposal = await _pending_proposal(session, case)
    await session.commit()
    state = _state(case)
    state.plan_proposal = proposal
    return state


@router.post("/intake/step/{step_name}/manual-entry", response_model=StepAck)
async def manual_entry(
    step_name: str,
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    if step_name not in INTAKE_STEPS:
        raise HTTPException(status_code=404, detail=f"unknown step: {step_name}")
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    merged = {
        _COVERAGE_ALIASES[k]: v for k, v in body.items() if k in _COVERAGE_ALIASES and v is not None
    }
    if merged:
        case.coverage = {**(case.coverage or {}), **merged}
    _advance(case, step_name)
    await session.commit()
    return _ack(case)


@router.post("/intake/step/{step_name}/skip", response_model=StepAck)
async def skip_step(
    step_name: str,
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    if step_name not in INTAKE_STEPS:
        raise HTTPException(status_code=404, detail=f"unknown step: {step_name}")
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    _advance(case, step_name)  # persists nothing for this step
    await session.commit()
    return _ack(case)


@router.post("/intake/step/insurance-card/extract", response_model=StepAck)
async def extract_insurance_card_step(
    req: ExtractRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """OCR an uploaded insurance card: persist high-confidence fields to coverage,
    return low-confidence fields as trivial yes/no confirmations (P1)."""
    case = await _resolve_case(session, user, req.case_file_id, create=True)
    fields = await extract_insurance_card(case.documents or [], req.document_id)
    high = fields.high_confidence_coverage()
    if high:
        case.coverage = {**(case.coverage or {}), **high}
    if case.intake_status != "complete":
        case.intake_status = "in_progress"
    await session.commit()
    return _ack(case, confirmations=fields.confirmations())


@router.post("/intake/visit-context", response_model=StepAck)
async def set_visit_context(
    req: VisitContextRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    case = await _resolve_case(session, user, req.case_file_id, create=True)
    case.visit_context = req.visit_context  # DL-54: stored verbatim; no CPT echoed back
    _advance(case, "visit-context")
    await session.commit()
    return _ack(case)


@router.post("/intake/complete", response_model=CompletionSummary)
async def complete_intake(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> CompletionSummary:
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    if _bills_count(case) == 0 and not _has_coverage(case):
        raise HTTPException(
            status_code=422,
            detail="Add at least one medical bill or your coverage details before finishing.",
        )
    case.intake_status = "complete"
    case.intake_current_step = "complete"
    await session.commit()

    cov = case.coverage or {}
    captured: list[str] = []
    if cov.get("payer_name") or cov.get("plan_name"):
        captured.append(f"Insurance plan: {cov.get('plan_name') or cov.get('payer_name')}")
    if cov.get("deductible_amount") is not None:
        captured.append(f"Deductible: ${cov['deductible_amount']:,.0f}")
    if cov.get("oop_max_amount") is not None:
        captured.append(f"Out-of-pocket max: ${cov['oop_max_amount']:,.0f}")
    if _bills_count(case):
        captured.append(f"{_bills_count(case)} medical bill(s)")
    if _eobs_count(case):
        captured.append(f"{_eobs_count(case)} EOB(s)")
    if case.visit_context:
        captured.append("A description of your visit")

    missing = _missing_items(case)
    summary = "Got it. Here's what I have, and what would unlock more if you add it later."
    return CompletionSummary(
        case_file_id=str(case.case_file_id),
        intake_status=case.intake_status,
        captured=captured,
        missing_items=missing,
        summary=summary,
    )


@router.post("/intake/plan-proposal/confirm", response_model=IntakeStateResponse)
async def confirm_plan_proposal(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> IntakeStateResponse:
    """Confirm a proposed plan-level design: write it through to coverage (canonical
    store), point plan_current at the entry, and increment the entry's confidence."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    entry = await _load_plan_entry(session, body.get("plan_library_id"))
    if entry is None:
        raise HTTPException(status_code=404, detail="plan_library entry not found")
    await plan_lib.confirm(session, entry, case)
    if case.intake_status != "complete":
        case.intake_status = "in_progress"
    await session.commit()
    return _state(case)


@router.post("/intake/plan-proposal/reject", response_model=IntakeStateResponse)
async def reject_plan_proposal(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> IntakeStateResponse:
    """Reject + (optionally) correct a proposed design: FORK a new PHI-stripped
    plan_library entry rather than overwriting; write the corrected design to
    coverage and archive the prior pointer into plan_history. `corrected_design` in
    the body holds the user's edits (stripped to benefit-design keys on write)."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    entry = await _load_plan_entry(session, body.get("plan_library_id"))
    if entry is None:
        raise HTTPException(status_code=404, detail="plan_library entry not found")
    await plan_lib.reject(session, entry, body.get("corrected_design") or {}, case)
    if case.intake_status != "complete":
        case.intake_status = "in_progress"
    await session.commit()
    return _state(case)
