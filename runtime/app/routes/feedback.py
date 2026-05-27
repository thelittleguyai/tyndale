"""POST /v1/feedback — persists a FeedbackEvent (L05 schema) and, when the user
has granted improvement consent, enqueues it for the security spine's de-id triage."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import FeedbackEvent, FeedbackTriageQueue
from app.db.session import get_session
from app.schemas.api_contract import FeedbackResponse
from app.schemas.feedback import FeedbackEventIn

router = APIRouter(tags=["v1"])


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    event: FeedbackEventIn,
    session: AsyncSession = Depends(get_session),
) -> FeedbackResponse:
    row = FeedbackEvent(
        case_file_id=event.case_file_id,
        user_id=event.user_id,
        response_id=event.response_id,
        feedback_type=event.feedback_type,
        improvement_consent=event.improvement_consent,
        payload=event.model_dump(mode="json"),
    )
    session.add(row)
    await session.flush()  # populate row.id

    queued = False
    if event.improvement_consent:
        # Per integration-contracts 2.4: consented events go to the triage queue;
        # the security spine's de-id runner reads from here (Phase 4).
        session.add(FeedbackTriageQueue(feedback_event_id=row.id))
        queued = True

    await session.commit()
    return FeedbackResponse(stored=True, feedback_event_id=str(row.id), queued_for_triage=queued)
