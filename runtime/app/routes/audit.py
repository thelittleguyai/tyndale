"""POST /v1/audit — runs the real Bill Detective + Math Person + Lead Planner
sequence and returns the AuditResult (three-number audit + findings + composed
markdown).

Falls back to the MRI fixture when USE_REAL_CLAUDE is off (or when the
Anthropic key is missing and allow_fixture_fallback is true) — that path
short-circuits inside ``orchestrator.run_audit``.

GET /v1/audit/{case_file_id} returns the current persisted state (idempotent
fetch — useful for the mobile app's polling pattern while the audit runs).

Both routes require an authenticated session and case ownership (security
fix: previously unauthenticated, exposing any case by UUID — IDOR).
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import _assemble_result, run_audit
from app.auth import CurrentUser, current_user
from app.db.session import get_session
from app.routes.case_access import require_case_owner
from app.schemas.api_contract import AuditRequest
from app.schemas.case_file import AuditResult, EobCompletenessOut, EobConfirmRequest
from app.sources.case_data import load_case_eobs_coverage
from app.sources.eob_completeness import summarize_eob_completeness

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/audit", response_model=AuditResult)
async def post_audit(
    req: AuditRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AuditResult:
    await require_case_owner(req.case_file_id, user, session)
    return await run_audit(req.case_file_id)


@router.get("/audit/{case_file_id}", response_model=AuditResult)
async def get_audit(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AuditResult:
    await require_case_owner(case_file_id, user, session)
    # Idempotent fetch: read the persisted findings and project to AuditResult.
    return await _assemble_result(case_file_id, composed="")


@router.get("/audit/{case_file_id}/eob-completeness", response_model=EobCompletenessOut)
async def get_eob_completeness(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> EobCompletenessOut:
    """The 'does that look like all of them?' summary (Sprint D, DL-86) — source-agnostic
    over whatever EOBs the case holds. Pure read; the POST confirms."""
    await require_case_owner(case_file_id, user, session)
    eobs, coverage = await load_case_eobs_coverage(case_file_id)
    return EobCompletenessOut(**summarize_eob_completeness(eobs, coverage).to_dict())


class CoverageInputRequest(BaseModel):
    """One checklist answer. ``field`` names a coverage number (deductible_amount,
    deductible_met, oop_max_amount, oop_max_met) or ``visit_confirm``; ``not_sure`` is the
    honest opt-out (acknowledged, never nagged, writes NO value)."""

    field: str
    value: float | str | None = None
    not_sure: bool = False


@router.post("/audit/{case_file_id}/coverage-input")
async def coverage_input(
    case_file_id: str,
    req: CoverageInputRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Checklist item save (Brock image-3 item 2). The value is a USER-ATTESTED fact:
    written into the case's coverage context with provenance (user-entered, timestamp) —
    the same blob the rung-2 sweep and the accumulator cross-validation read, so the
    audit's ranges tighten on the next derivation (rung-2 numbers are derived on read,
    never persisted). A later document that contradicts a user-entered value is the
    existing reconcile ladder's job."""
    from app.sources.coverage_checklist import COVERAGE_INPUT_FIELDS, VISIT_CONFIRM_KEY

    case = await require_case_owner(case_file_id, user, session)
    if req.field not in COVERAGE_INPUT_FIELDS:
        raise HTTPException(status_code=422, detail=f"unknown checklist field {req.field!r}")

    cov = dict(case.coverage or {})
    prov = dict(cov.get("user_input_provenance") or {})
    if not req.not_sure:
        if req.field == VISIT_CONFIRM_KEY:
            text = str(req.value or "").strip()
            if not (1 <= len(text) <= 200):
                raise HTTPException(status_code=422, detail="visit description must be 1–200 characters")
            cov["user_visit_description"] = text
        else:
            try:
                v = float(req.value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="value must be a number") from None
            if not (0 <= v <= 10_000_000):
                raise HTTPException(status_code=422, detail="value out of range")
            cov[req.field] = round(v, 2)
    prov[req.field] = {
        "source": "user-entered",
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "not_sure": bool(req.not_sure),
    }
    cov["user_input_provenance"] = prov
    case.coverage = cov
    await session.commit()
    # Re-render the checklist card in place (single card, updated state — DL-91 projection).
    from app.agents import thread_bridge

    await thread_bridge.bridge_case_state(case_file_id)
    if not req.not_sure:
        # image-3 item 4: the conversation reflects checklist progress — one line, no fanfare.
        from app.sources.coverage_checklist import label_for

        await thread_bridge.post_checklist_ack(case_file_id, label_for(req.field))
    return {"saved": req.field, "not_sure": bool(req.not_sure)}


class CoverageTextRequest(BaseModel):
    utterance: str


class CoverageTextResult(BaseModel):
    """D4(b) contract: mapping never writes state — the client PRE-SELECTS the checklist
    item + confirm chip and the confirming tap saves (POST coverage-input). mapped=False
    means the utterance is ordinary conversation: nothing was posted here, the client
    falls through to the normal chat send."""

    mapped: bool
    field: str | None = None
    value: float | None = None
    label: str | None = None
    result: str = "ok"  # ok | crisis | blocked
    conversation_id: str | None = None


@router.post("/audit/{case_file_id}/coverage-text", response_model=CoverageTextResult)
async def coverage_text(
    case_file_id: str,
    body: CoverageTextRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CoverageTextResult:
    """Free-text → checklist mapping (image-3 item 4): "my deductible is $2,000" pre-selects
    the matching coverage item. Same screen order as verify-text: crisis first (DL-04),
    then injection, then the deterministic mapper over the case's PENDING fields only."""
    from app.agents import thread_bridge
    from app.agents.verification_mapper import map_coverage_number
    from app.hooks.contracts import CrisisClassifierInput, UserPromptSubmitInput
    from app.hooks.crisis_classifier import crisis_classifier_async
    from app.hooks.user_prompt_submit import user_prompt_submit_hook
    from app.sources.coverage_checklist import coverage_checklist_items, label_for

    case = await require_case_owner(case_file_id, user, session)

    if (
        await crisis_classifier_async(CrisisClassifierInput(raw_message=body.utterance))
    ).crisis_detected:
        from app.agents.chat import _CRISIS_DECLINE

        await thread_bridge.post_user_utterance(case_file_id, body.utterance)
        cid = await thread_bridge.post_system_line(case_file_id, _CRISIS_DECLINE, tone="error")
        return CoverageTextResult(mapped=False, result="crisis", conversation_id=cid)

    ups = user_prompt_submit_hook(
        UserPromptSubmitInput(
            user_id=str(user.user_id), case_file_id=case_file_id,
            raw_message=body.utterance, attached_documents=[],
        )
    )
    if ups.block:
        cid = await thread_bridge.post_user_utterance(case_file_id, body.utterance)
        return CoverageTextResult(mapped=False, result="blocked", conversation_id=cid)

    pending = [
        i["key"] for i in coverage_checklist_items(case)
        if i["kind"] == "number" and i["value"] is None
    ]
    mapping = map_coverage_number(ups.scrubbed_message, pending)
    if mapping is None:
        return CoverageTextResult(mapped=False)  # ordinary chat — the client sends it there
    cid = await thread_bridge.post_user_utterance(case_file_id, ups.scrubbed_message)
    return CoverageTextResult(
        mapped=True, field=mapping.field, value=mapping.value,
        label=label_for(mapping.field), conversation_id=cid,
    )


@router.post("/audit/{case_file_id}/eob-completeness/confirm", response_model=EobCompletenessOut)
async def confirm_eob_completeness(
    case_file_id: str,
    req: EobConfirmRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> EobCompletenessOut:
    """User answers the completeness question. Confirm → all_plan_year_eobs_confirmed=true
    (the accumulator stops calling a partial pile complete). Not-all → park the case in
    awaiting_eob_confirmation and prompt for more uploads."""
    case = await require_case_owner(case_file_id, user, session)
    case.coverage = {**(case.coverage or {}), "all_plan_year_eobs_confirmed": req.all_uploaded}
    if not req.all_uploaded:
        case.status = "awaiting_eob_confirmation"
    elif case.status == "awaiting_eob_confirmation":
        case.status = "encounter_verified"  # unblocked; the audit may proceed
    await session.commit()
    # This route sets status directly (bypasses _set_status) — bridge the transition too (DL-91).
    from app.agents import thread_bridge

    await thread_bridge.bridge_case_state(case_file_id)
    eobs, coverage = await load_case_eobs_coverage(case_file_id)
    return EobCompletenessOut(**summarize_eob_completeness(eobs, coverage).to_dict())
