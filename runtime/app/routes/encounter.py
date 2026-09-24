"""Encounter-verification routes (Phase 2I).

The two-phase audit:
  POST /v1/audit/{id}/extract        -> Bill Detective translates line items
  GET  /v1/audit/{id}/line-items     -> idempotent fetch for the verification UI
  POST /v1/audit/{id}/confirmations  -> persist confirmations + kick finalize (bg)
  GET  /v1/audit/{id}/status         -> poll the case status

The existing GET /v1/audit/{id} (audit.py) stays the final-result fetch; the
mobile screen polls /status until 'audit_complete' before calling it.

All routes require an authenticated session and case ownership (security fix:
previously unauthenticated, exposing any case by UUID — IDOR).
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import (
    NotAwaitingConfirmations,
    extract_line_items,
    finalize_audit,
    submit_confirmations,
)
from app.auth import CurrentUser, current_user
from app.db.session import get_session
from app.routes.billing import require_active_subscription_or_free_slot
from app.routes.case_access import require_case_owner
from app.schemas.encounter import (
    AuditStatusResponse,
    ConfirmationsAccepted,
    ConfirmationsRequest,
    ExtractResult,
    VerifyTextRequest,
    VerifyTextResult,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/audit/{case_file_id}/extract", response_model=ExtractResult)
async def extract(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ExtractResult:
    await require_case_owner(case_file_id, user, session)
    return await extract_line_items(case_file_id)


@router.get("/audit/{case_file_id}/line-items", response_model=ExtractResult)
async def get_line_items(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ExtractResult:
    """Idempotent fetch — re-projects whatever line items are persisted without
    re-running the translate pass."""
    await require_case_owner(case_file_id, user, session)
    # Not extracted yet (or a prior extraction degraded) → extraction runs now; facts already
    # there → the same facts, never a second read (R1). Real mode returns the honest
    # extraction_failed result rather than fabricating fixture line items.
    return await extract_line_items(case_file_id)


@router.post("/audit/{case_file_id}/confirmations", response_model=ConfirmationsAccepted)
async def post_confirmations(
    case_file_id: str,
    body: ConfirmationsRequest,
    background: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    # Item 4 — audit creation gate. A pure no-op while enable_billing is False (dark scaffold);
    # when on, requires an active subscription or the one free analysis (DL-16).
    _billing: None = Depends(require_active_subscription_or_free_slot),
) -> ConfirmationsAccepted:
    case = await require_case_owner(case_file_id, user, session)
    # Attest-and-proceed gate (§A2 state 1): encounter verification cannot proceed while an
    # attestation is outstanding — the relationship must be on the record first.
    if case.attest_status == "required":
        raise HTTPException(status_code=409, detail="attestation required before verification")
    if case.attest_status == "declined":
        raise HTTPException(status_code=409, detail="case was closed by an authorization decline")
    if not body.confirmations:
        raise HTTPException(status_code=400, detail="confirmations must be non-empty")
    try:
        accepted = await submit_confirmations(case_file_id, body.confirmations)
    except NotAwaitingConfirmations:
        # R1: a finished (or running) audit is never restarted by a tap on a stale card
        raise HTTPException(status_code=409, detail="no pending verification for this case") from None
    if not accepted.audit_started:
        return accepted  # the same answers, re-sent — already on file; nothing starts twice
    # D8 / §4.4: a "not sure" answer is honest, never penalised — say so in the thread so the
    # user can see the audit is proceeding around it rather than blocked on it. Lazy import,
    # like every other bridge call site (the bridge is hooked FROM the orchestrator).
    from app.agents import thread_bridge as _bridge

    if any(c.response == "not_sure" for c in body.confirmations) and _bridge.enabled():
        await _bridge.post_not_sure_acknowledgment(case_file_id)
    # Internal analytics (P0): one verification_answered per line item, carrying the answer + its
    # position — this feeds the per-question "Not sure" rate (§2). Best-effort.
    from uuid import UUID as _UUID

    from app.analytics.emit import emit

    cf_uuid = _UUID(case_file_id)
    for i, conf in enumerate(body.confirmations):
        await emit("verification_answered", user_id=user.user_id, case_file_id=cf_uuid,
                   properties={"answer": conf.response, "question_position": i + 1})
    # Kick the finalize audit asynchronously; the UI polls /status.
    background.add_task(finalize_audit, case_file_id)
    return accepted


@router.get("/audit/{case_file_id}/status", response_model=AuditStatusResponse)
async def get_status(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AuditStatusResponse:
    cf = await require_case_owner(case_file_id, user, session)
    return AuditStatusResponse(case_file_id=case_file_id, status=cf.status)


async def _emit_analytics(name: str, user_id, case_file_id: str, props: dict | None = None) -> None:
    """Best-effort internal-analytics emit for the verify-text path (mapper + §6 counters)."""
    from uuid import UUID

    from app.analytics.emit import emit

    await emit(name, user_id=user_id, case_file_id=UUID(case_file_id), properties=props)


@router.post("/audit/{case_file_id}/verify-text", response_model=VerifyTextResult)
async def verify_text(
    case_file_id: str,
    body: VerifyTextRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> VerifyTextResult:
    """Chat-first D4b: map a free-text verification reply to a PRE-SELECTABLE suggestion. This NEVER
    commits — the confirming tap does (via /confirmations). Chat ingress (crisis, then injection)
    runs BEFORE the mapper, so a crisis-flagged message never reaches it. Only runs when the case
    has pending verification; otherwise free text is normal case chat (409)."""
    from app.config import get_settings

    if not get_settings().enable_chat_first_audit:
        raise HTTPException(status_code=404, detail="not found")  # endpoint hidden when flag off
    cf = await require_case_owner(case_file_id, user, session)

    from app.agents import thread_bridge
    from app.hooks.contracts import CrisisClassifierInput, UserPromptSubmitInput
    from app.hooks.crisis_classifier import crisis_classifier_async
    from app.hooks.user_prompt_submit import user_prompt_submit_hook

    # 1. Crisis screen FIRST (DL-04 precedence, untouched) — never reaches the mapper.
    if (
        await crisis_classifier_async(CrisisClassifierInput(raw_message=body.utterance))
    ).crisis_detected:
        from app.agents.chat import _CRISIS_DECLINE

        await thread_bridge.post_user_utterance(case_file_id, body.utterance)
        cid = await thread_bridge.post_system_line(case_file_id, _CRISIS_DECLINE, tone="error")
        await _emit_analytics("crisis_fire_count", user.user_id, case_file_id)
        return VerifyTextResult(result="crisis", conversation_id=cid)

    # 2. Injection screen (UserPromptSubmit).
    ups = user_prompt_submit_hook(
        UserPromptSubmitInput(
            user_id=str(user.user_id), case_file_id=case_file_id,
            raw_message=body.utterance, attached_documents=[],
        )
    )
    if ups.block:
        cid = await thread_bridge.post_user_utterance(case_file_id, body.utterance)
        await _emit_analytics("refusal_event", user.user_id, case_file_id, {"category": "other"})
        return VerifyTextResult(result="blocked", conversation_id=cid)
    utterance = ups.scrubbed_message

    # 3. Only maps while verification is pending — and only onto facts still unanswered (R1:
    # the card list comes from the one fact registry; an answered fact is never offered again).
    from app.agents import encounter_facts

    pending = encounter_facts.registry(cf).pending
    if cf.status != "encounter_verification_pending" or not pending:
        raise HTTPException(status_code=409, detail="no pending verification for this case")

    cid = await thread_bridge.post_user_utterance(case_file_id, utterance)

    from app.agents.verification_mapper import Card, map_verification, summarize_mappings

    cards = [
        Card(
            line_item_id=li["line_item_id"], ordinal=i + 1, code=li.get("code"),
            description=li.get("plain_language_translation") or li.get("raw_description"),
            amount=li.get("billed_amount"),
        )
        for i, li in enumerate(pending)
    ]
    result = await map_verification(utterance, cards)
    if result.mappable and result.mappings:
        summary = summarize_mappings(result.mappings, cards)
        # The mapper says 'unsure'; the confirmations vocabulary is 'not_sure' — convert at the
        # boundary so the client applies the suggestion directly to a LineItemResponse draft.
        await thread_bridge.post_verification_suggestion(
            case_file_id,
            [{"line_item_id": m.line_item_id,
              "intended_answer": "not_sure" if m.intended_answer == "unsure" else m.intended_answer}
             for m in result.mappings],
            summary,
        )
        await _emit_analytics("mapper_suggested", user.user_id, case_file_id)
        return VerifyTextResult(result="mapped", method=result.method, conversation_id=cid)
    await thread_bridge.post_verification_nudge(case_file_id, partial=result.partial)
    await _emit_analytics(
        "mapper_fallback", user.user_id, case_file_id,
        {"kind": "partial" if result.partial else "full"},
    )
    return VerifyTextResult(
        result="partial_fallback" if result.partial else "fallback",
        method=result.method, conversation_id=cid,
    )
