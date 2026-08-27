"""Feedback capture routes (Phase 2J).

- POST /v1/feedback — store a FeedbackEvent. The improvement_consent on the
  stored row is read from the users table at insert time, NOT trusted from the
  client. Consented events enqueue to feedback_triage_queue for the L06 de-id
  pipeline.
- GET /v1/feedback/case/{id} — events for a case (restore thumbs state in UI).
- GET /v1/feedback/outcome-prompts — cases eligible for an outcome prompt.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.routes.case_access import require_case_owner
from app.crons.outcome_followup import scan_for_outcome_followups
from app.db.models.feedback import FeedbackEvent, FeedbackTriageQueue
from app.db.models.users import User
from app.db.session import get_session
from app.schemas.feedback import (
    CaseFeedbackPayload,
    FeedbackAck,
    FeedbackEventIn,
    FeedbackEventOut,
    OutcomePrompt,
    OutcomePromptsPayload,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/feedback", response_model=FeedbackAck)
async def post_feedback(
    event: FeedbackEventIn,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> FeedbackAck:
    # IDOR fix (audit 2026-08-27 item 1): the body-supplied case_file_id was trusted, so any
    # authenticated user could write FeedbackEvents (incl. outcome_report amounts) against
    # another user's case and bump its last_outcome_check_at. Ownership first — 404, never
    # 403, per the anti-enumeration convention.
    await require_case_owner(event.case_file_id, user, session)

    # Read the user's CURRENT consent from the DB — never trust the client.
    db_user = (await session.execute(
        select(User).where(User.user_id == user.user_id)
    )).scalar_one()
    consent = bool(db_user.improvement_consent)

    payload = event.model_dump(mode="json")
    payload["improvement_consent"] = consent  # reflect the authoritative value

    row = FeedbackEvent(
        case_file_id=UUID(event.case_file_id),
        user_id=user.user_id,
        response_id=event.response_id,
        feedback_type=event.feedback_type,
        improvement_consent=consent,
        payload=payload,
    )
    session.add(row)
    await session.flush()  # populate row.id

    # A call-mode route tap stamps the same recency clock — the dashboard shouldn't ask "how
    # did it go?" the day after the user already told us. It does NOT write an outcome_report,
    # and that distinction is load-bearing: the follow-up scan retires a case PERMANENTLY once
    # an outcome_report exists, and none of the three call routes is an outcome ("they said
    # they'd fix it" is a claim by the party we're auditing). Suppressing on the recency clock
    # defers the real question by the follow-up window; writing an outcome_report would delete
    # it. The user still gets asked whether it actually worked.
    # One stamp, two triggers: an outcome_report retires the follow-up question; a call-route
    # tap only DEFERS it by the window (none of the three routes is an outcome — "they said
    # they'd fix it" is a claim by the party we're auditing; the scan's outcome_report check
    # is what makes retirement permanent, not this stamp).
    if event.call_outcome is not None or event.feedback_type == "outcome_report":
        from datetime import datetime, timezone

        from sqlalchemy import update

        from app.db.models.case_files import CaseFile

        await session.execute(
            update(CaseFile)
            .where(CaseFile.case_file_id == UUID(event.case_file_id))
            .values(last_outcome_check_at=datetime.now(timezone.utc))
        )

    queued = False
    if consent:
        session.add(FeedbackTriageQueue(feedback_event_id=row.id))
        queued = True

    await session.commit()

    # Internal analytics (P0). outcome_reported is IDEMPOTENT per case — a double-tapped outcome
    # button can never double-report (the win-rate denominator counts distinct cases, and the
    # aggregation reads the authoritative latest outcome for the numerator). Thumbs mirror into
    # finding_feedback. Best-effort; never affects the ack.
    from app.analytics.emit import emit, emit_idempotent

    case_uuid = UUID(event.case_file_id)
    if event.call_outcome is not None:
        # Idempotent per (case, call step): a double-tapped route can't inflate the
        # outcome-capture denominator. Carries the route only — no money, ever.
        await emit_idempotent(
            "call_outcome_recorded",
            dedupe_key=f"call_outcome_recorded:{case_uuid}:{event.response_id or 'case'}",
            user_id=user.user_id,
            case_file_id=case_uuid,
            properties={"route": event.call_outcome},
        )
    if event.feedback_type == "outcome_report":
        outcome = payload.get("outcome") or {}
        resolved = outcome.get("resolved")
        if resolved in ("yes", "partial", "no"):
            amount = outcome.get("amount_saved")
            amount = float(amount) if isinstance(amount, (int, float)) and not isinstance(amount, bool) else 0.0
            await emit_idempotent(
                "outcome_reported", dedupe_key=f"outcome_reported:{case_uuid}",
                user_id=user.user_id, case_file_id=case_uuid,
                properties={"resolved": resolved, "amount_saved": amount},
            )
    elif event.feedback_type == "thumbs":
        thumbs = payload.get("thumbs")
        if thumbs in ("up", "down"):
            await emit("finding_feedback", user_id=user.user_id, case_file_id=case_uuid,
                       properties={"thumbs": thumbs})

    return FeedbackAck(
        event_id=event.event_id,
        feedback_event_id=str(row.id),
        queued_for_deid=queued,
    )


@router.get("/feedback/case/{case_file_id}", response_model=CaseFeedbackPayload)
async def get_case_feedback(
    case_file_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> CaseFeedbackPayload:
    rows = (await session.execute(
        select(FeedbackEvent)
        .where(FeedbackEvent.case_file_id == UUID(case_file_id))
        .where(FeedbackEvent.user_id == user.user_id)
        .order_by(FeedbackEvent.created_at.asc())
    )).scalars().all()
    events = [
        FeedbackEventOut(
            feedback_event_id=str(r.id),
            feedback_type=r.feedback_type,
            response_id=r.response_id,
            thumbs=(r.payload or {}).get("thumbs"),
            structured_reason=(r.payload or {}).get("structured_reason"),
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
    return CaseFeedbackPayload(case_file_id=case_file_id, events=events)


@router.get("/feedback/outcome-prompts", response_model=OutcomePromptsPayload)
async def get_outcome_prompts(
    user: CurrentUser = Depends(current_user),
) -> OutcomePromptsPayload:
    followups = await scan_for_outcome_followups(user_id=str(user.user_id))
    return OutcomePromptsPayload(
        prompts=[
            OutcomePrompt(
                case_file_id=f.case_file_id,
                days_since_recommendation=f.days_since_recommendation,
                finding_summary=f.finding_summary,
            )
            for f in followups
        ]
    )
