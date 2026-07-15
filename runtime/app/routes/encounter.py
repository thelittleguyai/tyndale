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
    cf = await require_case_owner(case_file_id, user, session)
    if not cf.line_items:
        # Not extracted yet (or a prior extraction degraded) — run extraction now. It is
        # idempotent and, in real mode, returns the honest extraction_failed result rather
        # than fabricating fixture line items.
        return await extract_line_items(case_file_id)
    from app.agents.example_scenarios import backfill_scenarios
    from app.agents.orchestrator import _documents_projection
    from app.schemas.encounter import DEFAULT_INTRO_MESSAGE, LineItem

    # Phase 2L: backfill example scenarios for rows persisted before 2L.
    items = backfill_scenarios([dict(it) for it in cf.line_items])
    return ExtractResult(
        case_file_id=case_file_id,
        status="encounter_verification_pending",
        line_items=[LineItem(**it) for it in items],
        intro_message=DEFAULT_INTRO_MESSAGE,
        documents=_documents_projection(cf),
    )


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
    await require_case_owner(case_file_id, user, session)
    if not body.confirmations:
        raise HTTPException(status_code=400, detail="confirmations must be non-empty")
    accepted = await submit_confirmations(case_file_id, body.confirmations)
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
        return VerifyTextResult(result="blocked", conversation_id=cid)
    utterance = ups.scrubbed_message

    # 3. Only maps when verification is pending.
    if cf.status != "encounter_verification_pending" or not cf.line_items:
        raise HTTPException(status_code=409, detail="no pending verification for this case")

    cid = await thread_bridge.post_user_utterance(case_file_id, utterance)

    from app.agents.verification_mapper import Card, map_verification, summarize_mappings

    cards = [
        Card(
            line_item_id=li["line_item_id"], ordinal=i + 1, code=li.get("code"),
            description=li.get("plain_language_translation") or li.get("raw_description"),
            amount=li.get("billed_amount"),
        )
        for i, li in enumerate(cf.line_items)
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
        return VerifyTextResult(result="mapped", method=result.method, conversation_id=cid)
    await thread_bridge.post_verification_nudge(case_file_id, partial=result.partial)
    return VerifyTextResult(
        result="partial_fallback" if result.partial else "fallback",
        method=result.method, conversation_id=cid,
    )
