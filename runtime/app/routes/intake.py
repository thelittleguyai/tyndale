"""Guided intake routes — CO-1A's wizard, grown into the Intake Planner (doc 40, Phase 1).

CO-1A advanced through a FIXED step list. That list is gone: every endpoint here answers with
the PLANNER'S decision (``app.intake.planner`` — ``gap_list`` → ``next_screen`` over a screen
registry), recomputed after every capture and answer. The client holds no sequence and no copy:
it draws the ``screen`` it is handed (``app.intake.render``).

Every captured fact still lands where it always did — ``case_files.coverage`` (DL-52, the sole
source of the user's benefits state), ``attest_status``, ``encounter_confirmations``. The only new
store is ``case_files.intake_state``: the planner's own bookkeeping (skips, acks, the progress
high-water mark). Autosave is structural: every answer is one committed write, so "Save and exit"
saves nothing extra — it just leaves.

  GET  /v1/intake/state                  — the screen to draw (+ progress, resume). Creates NOTHING
  POST /v1/intake/start                  — open a guided case (intake_mode='guided')
  POST /v1/intake/answer                 — one answer from one screen → the next state
  POST /v1/intake/run                    — READY → run the audit → hand off to the existing reveal
  GET  /v1/intake/help                   — "Help me find it" (payer entry, else generic)
  POST /v1/intake/help/email             — the same steps, by email (the one send path)
  POST /v1/intake/step/{screen}/manual-entry | /skip, /step/insurance-card/extract,
       /step/coverage-regime-confirm/confirm, /visit-context, /guided-answers, /bill-check,
       /plan-proposal/confirm|reject, /complete, /benefits-doc-help — the CO-1A persistence
       seams, kept: same writes, but each now returns the planner's next state.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.models.plan_library import PlanLibraryEntry
from app.db.models.users import User
from app.db.session import get_session
from app.ingestion.bill_heuristics import detect_summary_bill
from app.ingestion.extract_documents import (
    _find_document,
    _ocr_text_for,
    extract_insurance_card,
)
from app.intake import planner as ip
from app.intake.render import group_copy, render_help, render_progress, render_screen, step
from app.intake.snapshot import COVERAGE_TYPE_OPTIONS, IntakeState, gather_inputs
from app.intake.timeline import eob_rows, persist_plan_year_start, plan_year_start_for
from app.routes.upload import BENEFITS_DOC_ALIASES
from app.schemas.intake import (
    CapturedData,
    CompletionSummary,
    ExtractRequest,
    HelpEmailRequest,
    IntakeAnswerRequest,
    IntakeHandoffRequest,
    IntakeProgress,
    IntakeResume,
    IntakeRunResponse,
    IntakeStateResponse,
    PlanProposal,
    RegimeConfirmRequest,
    StepAck,
    VisitContextRequest,
)
from app.services import plan_library as plan_lib
from app.sources.regime_detection import (
    detect_regime,
    is_valid_regime,
    signals_from_fields,
)

log = structlog.get_logger(__name__)
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

# CO-12C §4 guided-flow answers that merge into coverage: coordination of benefits,
# plan effective date, the all-plan-year-EOBs completeness signal (read by CO-12B's
# accumulator), and sibling-claim capture.
_GUIDED_COVERAGE_KEYS = (
    "has_secondary_coverage",
    "secondary_coverage_detail",
    "plan_effective_date",
    "plan_year",
    "all_plan_year_eobs_confirmed",
    "has_sibling_claims",
    "sibling_claim_date",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as e:
        raise HTTPException(status_code=422, detail="invalid case_file_id") from e


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


def _document_types(case: CaseFile) -> list[str]:
    return [d.get("document_type") for d in (case.documents or []) if d.get("document_type")]


def _apply_regime_detection(case: CaseFile) -> None:
    """Re-run deterministic regime detection from the case's current coverage +
    documents (Sprint B). Never overwrites a VERIFIED regime (user confirm or prior
    unambiguous evidence is sticky). Unambiguous high-confidence evidence auto-verifies
    and sets coverage_regime; anything less leaves coverage_regime null so the ladder
    asks — detection is never guessed into a silent default."""
    if (case.regime_detection or {}).get("verified"):
        return
    # A LOW-confidence card read is still evidence about WHICH KIND of coverage this is (a card
    # that says "MEDICARE HEALTH INSURANCE" should lead to the coverage-type question, not to
    # "who is your insurer?"). It can suggest a candidate; it can never verify a regime.
    fields = dict(case.coverage or {})
    weak_payer = (IntakeState(case).get("card_reads") or {}).get("payer_name")
    weak_only = bool(weak_payer and not fields.get("payer_name"))
    if weak_only:
        fields["payer_name"] = weak_payer
    detection = detect_regime(signals_from_fields(fields, _document_types(case)))
    if detection.regime is not None and detection.confidence == "high" and not weak_only:
        detection.verified = True
        case.coverage_regime = detection.regime
    else:
        case.coverage_regime = None
    case.regime_detection = detection.to_dict()
    # Brock 2026-07-06: persist any deterministically-detected coverage attributes (grandfathered,
    # qmb_status, …). Merge — never clobber a user-confirmed attribute with a null. PACE routes to a
    # graceful handoff (detection.handoff) rather than a regime; the intake surface reads it.
    if detection.attributes:
        merged = dict(case.coverage_attributes or {})
        merged.update({k: v for k, v in detection.attributes.items() if v is not None})
        case.coverage_attributes = merged


def _captured_data(case: CaseFile) -> CapturedData:
    return CapturedData(
        coverage=dict(case.coverage or {}),
        bills_count=_bills_count(case),
        eobs_count=_eobs_count(case),
        visit_context=case.visit_context,
        coverage_regime=case.coverage_regime,
        regime_detection=case.regime_detection,
    )


_ELAPSED_BUCKETS = ((10, "lt_10s"), (60, "lt_1m"), (300, "lt_5m"), (3600, "lt_1h"))


def _elapsed_bucket(since_iso: str | None) -> str:
    try:
        seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(str(since_iso))).total_seconds()
    except (TypeError, ValueError):
        return "unknown"
    return next((label for cap, label in _ELAPSED_BUCKETS if seconds < cap), "gt_1h")


async def _plan(
    session: AsyncSession, case: CaseFile, *, want_screen: str | None = None
) -> tuple[IntakeStateResponse, ip.PlannerInputs, str]:
    """THE chokepoint: snapshot → gap list → next screen → the wire state. Persists only what
    the planner owns — the current screen, the progress high-water mark, intake_status."""
    await _read_new_cards(case)  # infer first, then ask (§A4-1): a card is READ the moment it lands
    _apply_regime_detection(case)
    persist_plan_year_start(case)  # the retention anchor outlives the intake (doc 43, decision 9)
    proposal = await _pending_proposal(session, case)
    inputs = await gather_inputs(session, case, plan_proposal=proposal is not None)
    gaps = ip.gap_list(inputs)
    picked = ip.next_screen(inputs, gaps)
    # a readiness "edit" link asks for a specific screen — honoured only if this case has a use
    # for it; anything else falls back to the planner's pick
    screen_id = want_screen if (want_screen and ip.applicable(want_screen, inputs, gaps)) else picked
    if case.attest_status == "declined":
        screen_id = "attest"  # the decline ack; the flow is closed and says so

    st = IntakeState(case)
    live = ip.groups_satisfied(inputs, gaps)
    st.raise_high_water(live)  # the bar never regresses
    shown_changed = case.intake_current_step != picked
    case.intake_current_step = picked
    if case.intake_status == "not_started" and (inputs.bill_count or inputs.eob_count or st.acked):
        case.intake_status = "in_progress"
    if shown_changed:
        st.set("screen_shown_at", datetime.now(timezone.utc).isoformat())

    state = IntakeStateResponse(
        case_file_id=str(case.case_file_id),
        intake_status=case.intake_status,
        intake_mode=case.intake_mode,
        current_step=picked,
        completed_steps=render_progress(inputs, gaps, st.high_water)["high_water"],
        screen=render_screen(screen_id, case, inputs, gaps, proposal=proposal),
        progress=IntakeProgress(**render_progress(inputs, gaps, st.high_water)),
        chrome=group_copy("chrome"),
        captured_data=_captured_data(case),
        missing_items=_missing_items(case),
        plan_proposal=proposal,
    )
    if shown_changed and case.intake_mode == "guided":
        await _emit_shown(case, picked, inputs)
    return state, inputs, picked


_CARD_FIELD = {"payer": "payer_name"}  # the extractor's confirmation names → coverage keys


async def _read_new_cards(case: CaseFile) -> None:
    """Every insurance card on the case is read ONCE, as soon as the planner next looks at the
    case: high-confidence fields land in coverage (so "which insurer?" is never asked of someone
    whose card said it), low-confidence ones are left for the user. Reads the OCR text stored at
    upload — no second OCR call. The client orchestrates nothing."""
    st = IntakeState(case)
    done = set(st.get("cards_read") or [])
    fresh = [
        d for d in (case.documents or [])
        if isinstance(d, dict) and d.get("document_type") == "insurance_card"
        and d.get("document_id") and str(d["document_id"]) not in done
    ]  # fmt: skip
    weak: dict[str, str] = dict(st.get("card_reads") or {})
    for d in fresh:
        try:
            fields = await extract_insurance_card(case.documents or [], str(d["document_id"]))
            high = fields.high_confidence_coverage()
            unsure = {_CARD_FIELD.get(c["field"], c["field"]): str(c["read_value"]) for c in fields.confirmations()}
        except Exception as e:  # noqa: BLE001 — an unreadable card must never block the intake
            log.warning("intake.card_read_failed", case_file_id=str(case.case_file_id), error=str(e))
            high, unsure = {}, {}
        if high:
            # never overwrite what the user typed or a prior document supplied
            case.coverage = {**high, **{k: v for k, v in (case.coverage or {}).items() if v is not None}}
        # A low-confidence read is never a silent value — and never thrown away either: the
        # `insurer` screen shows it for the user to confirm or fix (CO-1A's confirmation
        # prompts, kept; this is not the §A9 scanning work).
        weak.update({k: v for k, v in unsure.items() if k in ("payer_name", "member_id") and v})
        done.add(str(d["document_id"]))
    if fresh:
        st.set("cards_read", sorted(done))
        if weak:
            st.set("card_reads", weak)


async def _emit_shown(case: CaseFile, screen_id: str, inputs: ip.PlannerInputs) -> None:
    """Funnel analytics: enum + counts only — never a value (§ item 8)."""
    from app.analytics.emit import emit

    await emit("intake_screen_shown", user_id=case.user_id, case_file_id=case.case_file_id,
               properties={"screen": screen_id if screen_id in ip.SCREEN_IDS else "ready"})
    if screen_id == "handoff":
        await emit("intake_handoff", user_id=case.user_id, case_file_id=case.case_file_id,
                   properties={"population": inputs.population or "other"})


async def _ack(
    session: AsyncSession, case: CaseFile, confirmations: list[dict] | None = None
) -> StepAck:
    state, _, _ = await _plan(session, case)
    await session.commit()
    return StepAck(**state.model_dump(), confirmations=confirmations or [])


async def _resolve_case(
    session: AsyncSession,
    user: CurrentUser,
    case_file_id: str | None,
    *,
    create: bool = False,
) -> CaseFile:
    """The case an intake write is about. An explicit id is ownership-checked (404, never a
    leak). With no id this is the CO-1A seam Settings still uses — the user's most recent case,
    created if they have none; the GUIDED route never relies on it (it always passes the id
    POST /intake/start returned)."""
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
        cf = CaseFile(user_id=user.user_id, status="open", intake_status="not_started")
        session.add(cf)
        await session.flush()
    if cf is None:
        raise HTTPException(status_code=404, detail="no case file for user")
    return cf


async def _unfinished_guided_case(session: AsyncSession, user: CurrentUser) -> CaseFile | None:
    return (
        await session.execute(
            select(CaseFile)
            .where(CaseFile.user_id == user.user_id)
            .where(CaseFile.intake_mode == "guided")
            .where(CaseFile.intake_status == "in_progress")
            .where(CaseFile.soft_deleted_at.is_(None))
            .order_by(CaseFile.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _fresh_state() -> IntakeStateResponse:
    """The landing, before anything exists. Opening /intake creates NO case — a user who looks
    and leaves must not litter the Record (or the review queue) with empty ones."""
    empty = ip.PlannerInputs()
    gaps = ip.gap_list(empty)
    return IntakeStateResponse(
        case_file_id=None,
        intake_status="not_started",
        current_step="welcome",
        screen=render_screen("welcome", CaseFile(documents=[], eobs=[], line_items=[]), empty, gaps),
        progress=IntakeProgress(**render_progress(empty, gaps, [])),
        chrome=group_copy("chrome"),
        captured_data=CapturedData(),
    )


def _resume_block(case: CaseFile, state: IntakeStateResponse) -> IntakeResume:
    """§C7. The expiry line states the REAL magic-link lifetime from Settings — never a promise
    the auth layer does not keep (a long-lived resume link is a security decision, not copy)."""
    group = state.screen.get("progress_group")
    label = next(
        (s.get("label") for s in state.progress.segments if s.get("group") == group), None
    ) or step("intake.readiness.title")
    return IntakeResume(
        case_file_id=str(case.case_file_id),
        title=step("intake.resume.title"),
        body=step("intake.resume.body", group_label=label or ""),
        primary=step("intake.resume.primary"),
        new=step("intake.resume.new"),
        link_expiry=step("intake.resume.link_expiry", minutes=get_settings().magic_link_ttl_minutes),
    )


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
# The planner's routes
# --------------------------------------------------------------------------- #
@router.get("/intake/state", response_model=IntakeStateResponse)
async def get_intake_state(
    case_file_id: str | None = None,
    screen: str | None = None,
    latest: bool = False,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> IntakeStateResponse:
    """The screen to draw. With an id: that case (``screen=`` asks for a specific one — the
    readiness edit links). With none: the user's unfinished guided case as a "pick up where you
    left off" landing (§C7), else the welcome — and NOTHING is created. ``latest=true`` is the
    CO-1A seam Settings' coverage-type row uses (most recent case, created if none)."""
    if case_file_id or latest:
        case = await _resolve_case(session, user, case_file_id, create=latest)
        state, _, _ = await _plan(session, case, want_screen=screen)
        await session.commit()
        return state
    case = await _unfinished_guided_case(session, user)
    if case is None:
        return _fresh_state()
    state, _, _ = await _plan(session, case)
    state.resume = _resume_block(case, state)
    await session.commit()
    return state


@router.post("/intake/start", response_model=StepAck)
async def start_intake(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """Open a guided case. THIS is what stamps ``intake_mode='guided'`` — the front door is a
    fact about how the case was opened, recorded where it happens (doc 40 §D)."""
    case = CaseFile(
        user_id=user.user_id, status="open", intake_status="in_progress", intake_mode="guided"
    )
    session.add(case)
    await session.flush()
    IntakeState(case).ack("welcome")
    from app.analytics.emit import emit

    ack = await _ack(session, case)
    await emit("intake_started", user_id=user.user_id, case_file_id=case.case_file_id)
    return ack


def _money(value: Any, *, field: str) -> float:
    try:
        n = float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"{field}: not a dollar amount") from e
    if not 0 <= n <= 10_000_000:
        raise HTTPException(status_code=422, detail=f"{field}: out of range")
    return round(n, 2)


def _user_entered(case: CaseFile, key: str, *, value: float | None, not_sure: bool = False) -> None:
    """Write a user-attested coverage number with the SAME provenance shape the coverage
    checklist writes (routes/audit.py coverage-input) — a later document that contradicts it is
    the reconcile ladder's job, never a silent overwrite."""
    cov = dict(case.coverage or {})
    prov = dict(cov.get("user_input_provenance") or {})
    prov[key] = {
        "source": "user-entered",
        "at": datetime.now(timezone.utc).isoformat(),
        "not_sure": bool(not_sure),
    }
    if value is not None:
        cov[key] = value
    cov["user_input_provenance"] = prov
    case.coverage = cov


async def _apply_answer(  # noqa: PLR0912, PLR0915
    session: AsyncSession, case: CaseFile, user: CurrentUser, req: IntakeAnswerRequest
) -> None:
    """One screen's answer → the store that owns it. Screens with no engine home (acks, skips,
    the plain coverage-type answer) go to intake_state; everything else lands where CO-1A, the
    checklist and the attest spine already put it."""
    st = IntakeState(case)
    sid, action, v = req.screen, req.action, req.values
    if sid not in ip.SCREENS:
        raise HTTPException(status_code=404, detail=f"unknown screen: {sid}")
    screen = ip.SCREENS[sid]

    if action == "skip":
        if not screen.skippable:
            raise HTTPException(status_code=422, detail=f"{sid} cannot be skipped")
        if sid in ("deductible_met", "oop_met"):
            _user_entered(case, "deductible_met" if sid == "deductible_met" else "oop_max_met",
                          value=None, not_sure=True)
        if sid == "bill_itemized":
            st.ack(sid)  # "keep going with this bill" — coached once, never nagged
        st.skip(sid)
        return

    if sid in ("welcome", "facts_only", "readiness", "reading"):
        st.ack(sid)
    elif sid in ("bill", "eob", "card", "plan_rules", "bill_itemized"):
        st.unskip(sid)  # a capture happened (the upload itself is POST /v1/upload with this id)
        if sid == "bill_itemized":
            st.ack(sid)
    elif sid == "bill_summary":
        if action == "fix":
            return  # the client re-opens capture; nothing to record
        if action == "yes":  # other bills for this same visit → attach to the SAME case (§C1)
            case.coverage = {**(case.coverage or {}), "has_sibling_claims": True}
            st.set("expecting_more_bills", True)
            return  # stays on the read-back until the user says "that's all"
        case.coverage = {**(case.coverage or {}), "has_sibling_claims": bool(st.get("expecting_more_bills"))}
        st.ack(sid)
    elif sid == "insurer":
        payer = str(v.get("payer_name") or "").strip()[:120]
        member = str(v.get("member_id") or "").strip()[:64]
        if not payer:
            raise HTTPException(status_code=422, detail="payer_name is required")
        case.coverage = {**(case.coverage or {}), "payer_name": payer, **({"member_id": member} if member else {})}
    elif sid == "coverage_type":
        choice = str(v.get("choice") or "")
        if choice not in COVERAGE_TYPE_OPTIONS:
            raise HTTPException(status_code=422, detail="unknown coverage type")
        st.answer("coverage_type", choice)
    elif sid == "plan_year":
        choice = str(v.get("choice") or "")
        if choice == "not_sure":
            st.skip(sid)
        else:
            try:
                month = int(choice)
                assert 1 <= month <= 12
            except (ValueError, AssertionError) as e:
                raise HTTPException(status_code=422, detail="month must be 1–12") from e
            start = plan_year_start_for(month, case.date_of_service)
            case.coverage = {**(case.coverage or {}), "plan_effective_date": start,
                             "plan_year": int(start[:4])}
            st.unskip(sid)
    elif sid == "timeline":
        if action not in ("yes", "no"):
            raise HTTPException(status_code=422, detail="answer yes or no")
        # the EXISTING completeness signal CO-12B's accumulator reads — and the count it was
        # given against, so adding an EOB afterwards asks again (locked 5d: EVERY time)
        case.coverage = {**(case.coverage or {}), "all_plan_year_eobs_confirmed": action == "yes"}
        st.set("completeness_at_count", len(eob_rows(case)))
    elif sid in ("deductible_met", "oop_met"):
        key = "deductible_met" if sid == "deductible_met" else "oop_max_met"
        if action == "not_sure":
            _user_entered(case, key, value=None, not_sure=True)
        else:
            _user_entered(case, key, value=_money(v.get(key), field=key))
        st.unskip(sid)
    elif sid == "other_insurance":
        choice = str(v.get("choice") or action)
        if choice not in ("yes", "no", "not_sure"):
            raise HTTPException(status_code=422, detail="answer yes, no or not_sure")
        if choice == "not_sure":
            st.skip(sid)
        else:
            case.coverage = {**(case.coverage or {}), "has_secondary_coverage": choice == "yes"}
    elif sid == "confirmations":
        await _save_confirmations(case, v.get("confirmations") or [])
    elif sid in ("attest", "plan_rules_confirm", "handoff"):
        # attest → POST /v1/case/{id}/attest[/decline]; plan → /intake/plan-proposal/*; the
        # handoff → POST /intake/handoff. Each is its own audited route — not re-implemented here.
        raise HTTPException(status_code=422, detail=f"{sid} is answered through its own route")


async def _save_confirmations(case: CaseFile, raw: list) -> None:
    """The encounter facts, through the EXISTING submit path (a "no" becomes an
    encounter_mismatch finding there) — but WITHOUT starting the audit: on the guided route the
    readiness screen comes first, and POST /intake/run is what runs it."""
    from app.agents.encounter_facts import registry
    from app.agents.orchestrator import NotAwaitingConfirmations, submit_confirmations
    from app.schemas.encounter import LineItemConfirmation

    if case.attest_status == "required":
        raise HTTPException(status_code=409, detail="attestation required before verification")
    # the screen asked for the facts nobody has answered yet — exactly those come back (R1)
    known = {li.get("line_item_id") for li in registry(case).pending}
    try:
        confs = [LineItemConfirmation(**c) for c in raw]
    except Exception as e:  # noqa: BLE001 — pydantic's message is the useful part
        raise HTTPException(status_code=422, detail=f"bad confirmation: {e}") from e
    if not confs or {c.line_item_id for c in confs} != known:
        # never capped, never padded (§A4-5): one answer per fact the engine emitted
        raise HTTPException(status_code=422, detail="answer every fact, and only those")
    try:
        await submit_confirmations(str(case.case_file_id), confs)
    except NotAwaitingConfirmations:
        raise HTTPException(status_code=409, detail="no pending verification for this case") from None


@router.post("/intake/answer", response_model=StepAck)
async def answer(
    req: IntakeAnswerRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    case = await _resolve_case(session, user, req.case_file_id)
    shown_at = IntakeState(case).get("screen_shown_at")
    await _apply_answer(session, case, user, req)
    await session.commit()  # autosave IS this commit — every answer, before anything else
    await session.refresh(case)
    from app.analytics.emit import emit
    from app.analytics.events import coerce_enum

    await emit(
        "intake_screen_action",
        user_id=user.user_id,
        case_file_id=case.case_file_id,
        properties={
            "screen": req.screen,
            "action": coerce_enum("intake_screen_action", "action", req.action),
            "elapsed": _elapsed_bucket(shown_at),
        },
    )
    ack = await _ack(session, case)
    if ack.current_step == "reading":
        _kick_extraction(case, background)
    return ack


def _kick_extraction(case: CaseFile, background: BackgroundTasks) -> None:
    """The engine reads the bill (Bill Detective, translate mode) while the user keeps going —
    once per case; the planner's `reading` screen polls /intake/state until the facts land."""
    from app.agents.orchestrator import _stale_extraction, extract_line_items

    st = IntakeState(case)
    if st.get("extraction_started_at") and not _stale_extraction(case):
        return  # once per case — unless that read died (in_progress, silent for 10 min)

    st.set("extraction_started_at", datetime.now(timezone.utc).isoformat())
    background.add_task(extract_line_items, str(case.case_file_id))


@router.post("/intake/run", response_model=IntakeRunResponse)
async def run_intake(
    background: BackgroundTasks,
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> IntakeRunResponse:
    """READY → run the audit and hand off to the EXISTING results surfaces. The guided route
    builds no results UI: the three numbers, the findings with their side attribution, the
    unlock moment, the gameplan, call mode and chat are the shared components (§C2)."""
    from app.agents.orchestrator import finalize_audit

    case = await _resolve_case(session, user, body.get("case_file_id"))
    state, inputs, picked = await _plan(session, case)
    if picked != ip.READY:
        raise HTTPException(status_code=409, detail=f"not ready: next is {picked}")
    if not (inputs.bill_count or inputs.eob_count):
        raise HTTPException(status_code=422, detail="add a bill or an insurer statement first")
    case.intake_status = "complete"
    case.intake_current_step = ip.READY
    await session.commit()
    cfid = str(case.case_file_id)

    # The thread is the shared post-analysis surface (reveal, unlock, gameplan, chat): give the
    # guided case the same one an upload gets. Flag-gated no-op when chat-first is off.
    from app.agents.thread_bridge import bootstrap_thread

    conversation_id = await bootstrap_thread(cfid)
    background.add_task(finalize_audit, cfid)
    from app.analytics.emit import emit

    gaps = ip.gap_list(inputs)
    await emit("intake_audit_started", user_id=user.user_id, case_file_id=case.case_file_id,
               properties={"unresolved": len(gaps.open_keys())})
    return IntakeRunResponse(
        case_file_id=cfid,
        status="audit_running",
        next_route=f"/audit/{cfid}/thread" if conversation_id else f"/audit/{cfid}",
        conversation_id=conversation_id,
    )


@router.post("/intake/handoff", response_model=IntakeRunResponse)
async def handoff_intake(
    req: IntakeHandoffRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> IntakeRunResponse:
    """The guided route's OTHER exit (§A4-4): a coverage population Phase 1 does not carry leaves
    for the chat-first flow. This CLOSES the guided intake for the case — otherwise the home
    card and /intake keep inviting the user back to a route that cannot take them — and says
    where chat-first picks the case up, using chat-first's own entry points:

    - documents on the case → its thread (the upload path's `bootstrap_thread`), or — with the
      chat-first audit off — the classic read-then-verify screen, exactly as an upload would;
    - nothing uploaded yet  → the upload screen, which calls this again once a document lands.

    Idempotent. `case_files.intake_mode` stays "guided": it records the door the case was
    OPENED through, and `intake_state.handed_off` records that it left (population enum)."""
    from app.agents.orchestrator import extract_line_items
    from app.agents.thread_bridge import bootstrap_thread

    case = await _resolve_case(session, user, req.case_file_id)
    if not IntakeState(case).get("handed_off"):
        _, inputs, picked = await _plan(session, case)
        if picked != "handoff":
            raise HTTPException(status_code=409, detail=f"not a handoff: next is {picked}")
        IntakeState(case).set("handed_off", inputs.population or "other")
        case.intake_status = "complete"
    await session.commit()

    cfid = str(case.case_file_id)
    if not any(isinstance(d, dict) for d in (case.documents or [])):
        return IntakeRunResponse(case_file_id=cfid, status=case.status,
                                 next_route=f"/upload?caseId={cfid}&handoff=1")
    conversation_id = await bootstrap_thread(cfid)  # flag-gated no-op when chat-first is off
    if conversation_id:
        return IntakeRunResponse(case_file_id=cfid, status=case.status,
                                 next_route=f"/audit/{cfid}/thread", conversation_id=conversation_id)
    if not case.line_items:  # classic flow: the verify screen expects the bill already read
        await extract_line_items(cfid)
    return IntakeRunResponse(case_file_id=cfid, status=case.status, next_route=f"/audit/{cfid}/encounter")


@router.get("/intake/help")
async def intake_help(
    document_type: str,
    case_file_id: str | None = None,
    screen: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> dict[str, Any]:
    """"Help me find it" (§A5): the payer's own path when a document named the payer and the
    corpus has it, else the generic steps."""
    payer = None
    if case_file_id:
        case = await _resolve_case(session, user, case_file_id)
        payer = (case.coverage or {}).get("payer_name")
    found = render_help(payer, document_type, screen)
    if found is None:
        raise HTTPException(status_code=404, detail="no instructions for that document type")
    return found


@router.post("/intake/help/email")
async def email_intake_help(
    req: HelpEmailRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> dict[str, Any]:
    """The same steps by email — users leave the app to go to the portal (locked 5c). ONE send
    path (notify.email.send_product_email): the DL-47 PHI guard and the synthetic-suffix guard
    both apply. The body is generic navigation steps + the payer's NAME — no claim, no amount,
    no document content. SMS is not built and is not offered."""
    from app.notify.email import FOOTER, send_product_email

    payer = None
    if req.case_file_id:
        case = await _resolve_case(session, user, req.case_file_id)
        payer = (case.coverage or {}).get("payer_name")
    found = render_help(payer, req.document_type, req.screen)
    if found is None:
        raise HTTPException(status_code=404, detail="no instructions for that document type")
    urow = (await session.execute(select(User).where(User.user_id == user.user_id))).scalar_one()
    lines = [step("intake.help.email_intro") or "", "", found["title"] or "", found["note"] or "", ""]
    lines += [f"{n}. {text}" for n, text in enumerate(found["steps"], start=1)]
    sent = await send_product_email(
        urow.email,
        step("intake.help.email_subject") or "Your steps from Tyndale",
        "\n".join([*lines, "", FOOTER]),
        kind="intake_help",
    )
    from app.analytics.emit import emit
    from app.analytics.events import coerce_enum

    await emit("intake_help_emailed", user_id=user.user_id,
               case_file_id=_uuid(req.case_file_id) if req.case_file_id else None,
               properties={"document_type": coerce_enum("intake_help_emailed", "document_type", req.document_type),
                           "scope": found["scope"], "sent": bool(sent)})
    return {"sent": bool(sent), "message": step("intake.chrome.email_sent" if sent else "intake.chrome.email_failed")}


# --------------------------------------------------------------------------- #
# The CO-1A persistence seams — same writes; each now answers with the planner's next state
# --------------------------------------------------------------------------- #
@router.post("/intake/step/{step_name}/manual-entry", response_model=StepAck)
async def manual_entry(
    step_name: str,
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """Persist typed coverage fields (card corrections, plan numbers). The step NAME no longer
    decides anything — there is no sequence to advance — so any name is accepted."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    merged = {
        _COVERAGE_ALIASES[k]: v for k, v in body.items() if k in _COVERAGE_ALIASES and v is not None
    }
    if merged:
        case.coverage = {**(case.coverage or {}), **merged}
    if case.intake_status == "not_started":
        case.intake_status = "in_progress"
    return await _ack(session, case)


@router.post("/intake/step/{step_name}/skip", response_model=StepAck)
async def skip_step(
    step_name: str,
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """Skip a screen — persists nothing but the skip itself, and only for a screen the registry
    marks skippable (a CO-1A step name that is not a registry screen is a no-op)."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    screen = ip.SCREENS.get(step_name)
    if screen is not None and screen.skippable:
        IntakeState(case).skip(step_name)
    return await _ack(session, case)


@router.post("/intake/step/insurance-card/extract", response_model=StepAck)
async def extract_insurance_card_step(
    req: ExtractRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """OCR an uploaded insurance card: persist high-confidence fields to coverage, return
    low-confidence fields as trivial yes/no confirmations (P1). The planner then SKIPS whatever
    the card answered — a card that named the payer means no "which insurer" screen."""
    case = await _resolve_case(session, user, req.case_file_id, create=True)
    fields = await extract_insurance_card(case.documents or [], req.document_id)
    high = fields.high_confidence_coverage()
    if high:
        case.coverage = {**(case.coverage or {}), **high}
    if case.intake_status == "not_started":
        case.intake_status = "in_progress"
    return await _ack(session, case, confirmations=fields.confirmations())


@router.post("/intake/step/coverage-regime-confirm/confirm", response_model=StepAck)
async def confirm_coverage_regime(
    req: RegimeConfirmRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """The verification-ladder answer to 'How are you covered?' — an explicit user confirm
    sets the regime verified (Sprint B, DL-82). Settings' coverage-type row uses this; on the
    guided route the plain-language coverage_type screen is the ask, and a non-commercial
    regime confirmed here exits the route exactly as a detected one does."""
    if not is_valid_regime(req.coverage_regime):
        raise HTTPException(status_code=422, detail="invalid coverage_regime")
    case = await _resolve_case(session, user, req.case_file_id, create=True)
    case.coverage_regime = req.coverage_regime
    prior_evidence = list((case.regime_detection or {}).get("evidence") or [])
    prior_evidence.append("user confirmed coverage regime on the intake ladder")
    case.regime_detection = {
        "regime": req.coverage_regime,
        "candidate": req.coverage_regime,
        "confidence": "high",
        "method": "user_declared",
        "evidence": prior_evidence,
        "verified": True,
    }
    return await _ack(session, case)


@router.post("/intake/visit-context", response_model=StepAck)
async def set_visit_context(
    req: VisitContextRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    case = await _resolve_case(session, user, req.case_file_id, create=True)
    case.visit_context = req.visit_context  # DL-54: stored verbatim; no CPT echoed back
    return await _ack(session, case)


@router.post("/intake/complete", response_model=CompletionSummary)
async def complete_intake(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> CompletionSummary:
    """Mark intake complete WITHOUT running the audit (the CO-1A seam; the guided route uses
    POST /intake/run). Still refuses an intake with nothing in it."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    if _bills_count(case) == 0 and not _has_coverage(case):
        raise HTTPException(
            status_code=422,
            detail="Add at least one medical bill or your coverage details before finishing.",
        )
    case.intake_status = "complete"
    case.intake_current_step = ip.READY
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
    return CompletionSummary(
        case_file_id=str(case.case_file_id),
        intake_status=case.intake_status,
        captured=captured,
        missing_items=_missing_items(case),
        summary=step("intake.readiness.title") or "",
    )


@router.post("/intake/plan-proposal/confirm", response_model=StepAck)
async def confirm_plan_proposal(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """Confirm a proposed plan-level design: write it through to coverage (canonical store),
    point plan_current at the entry, and increment the entry's confidence. The planner then
    finds the plan rules resolved — the SBC upload screen never appears."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    entry = await _load_plan_entry(session, body.get("plan_library_id"))
    if entry is None:
        raise HTTPException(status_code=404, detail="plan_library entry not found")
    await plan_lib.confirm(session, entry, case)
    if case.intake_status == "not_started":
        case.intake_status = "in_progress"
    return await _ack(session, case)


@router.post("/intake/plan-proposal/reject", response_model=StepAck)
async def reject_plan_proposal(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """Reject + (optionally) correct a proposed design: FORK a new PHI-stripped plan_library
    entry rather than overwriting; write the corrected design to coverage and archive the prior
    pointer into plan_history. `corrected_design` holds the user's edits."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    entry = await _load_plan_entry(session, body.get("plan_library_id"))
    if entry is None:
        raise HTTPException(status_code=404, detail="plan_library entry not found")
    await plan_lib.reject(session, entry, body.get("corrected_design") or {}, case)
    if case.intake_status == "not_started":
        case.intake_status = "in_progress"
    return await _ack(session, case)


# --------------------------------------------------------------------------- #
# Guided flows (CO-12C §4)
# --------------------------------------------------------------------------- #
@router.post("/intake/guided-answers", response_model=StepAck)
async def guided_answers(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> StepAck:
    """Persist the §4 guided-flow answers into coverage: coordination of benefits
    (has_secondary_coverage), plan effective date / plan year (anchors CO-12B's plan-year
    filtering on real dates), sibling-claim capture, and the all_plan_year_eobs_confirmed
    completeness signal CO-12B's accumulator reads."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    merged = {k: body[k] for k in _GUIDED_COVERAGE_KEYS if k in body and body[k] is not None}
    if merged:
        case.coverage = {**(case.coverage or {}), **merged}
        if "all_plan_year_eobs_confirmed" in merged:
            IntakeState(case).set("completeness_at_count", len(eob_rows(case)))
    if case.intake_status == "not_started":
        case.intake_status = "in_progress"
    return await _ack(session, case)


@router.post("/intake/bill-check")
async def bill_check(
    body: dict[str, Any] = Body(default_factory=dict),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> dict[str, Any]:
    """Summary-bill detection: flag a bill that looks like a summary (no line-level
    CPT/HCPCS, round totals, balance-forward) and return a script to request an
    itemized bill. Non-blocking — guidance only."""
    case = await _resolve_case(session, user, body.get("case_file_id"), create=True)
    doc = _find_document(case.documents or [], str(body.get("document_id", ""))) or {}
    return detect_summary_bill(await _ocr_text_for(doc))


@router.get("/intake/benefits-doc-help")
async def benefits_doc_help(
    user: CurrentUser = Depends(current_user),
) -> dict[str, Any]:
    """The benefits document goes by many names — surface them (the SBC screen's "Help me find
    it" carries the steps; this stays for the aliases)."""
    help_ = render_help(None, "sbc") or {}
    return {
        "aliases": list(BENEFITS_DOC_ALIASES),
        "help_copy": step("intake.plan_rules.body"),
        "cannot_find_copy": step("intake.plan_rules.skip_consequence"),
        "steps": help_.get("steps", []),
    }
