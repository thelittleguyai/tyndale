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

    # If this is an outcome_report, stamp the case so the dashboard stops
    # re-prompting.
    if event.feedback_type == "outcome_report":
        from app.db.models.case_files import CaseFile
        from sqlalchemy import update
        from datetime import datetime, timezone

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
