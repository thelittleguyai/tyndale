"""POST /v1/events — the batched, authenticated client event ingress (Internal Analytics P0).

Only events that are NOT server-known belong here; server-known funnel events are emitted
server-side and rejected if a client tries to assert them (``server_only``). Unknown, server-only,
and not-yet-live names are silently dropped and counted (never a per-event 4xx). Rate-limited per
user to bound abuse; the whole endpoint is best-effort and never blocks on analytics durability.
"""

from __future__ import annotations

import datetime

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.emit import DROP_COUNTER
from app.analytics.events import REGISTRY, EventValidationError, validate_event
from app.auth import CurrentUser, current_user
from app.db.models.analytics_events import AnalyticsEvent
from app.db.session import get_session
from app.schemas.events import EventBatch, EventBatchResult

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

# Generous per-user hourly cap — analytics is high-volume but a runaway client shouldn't flood.
EVENTS_PER_HOUR = 1000


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def _user_event_count_last_hour(session: AsyncSession, user_id) -> int:
    cutoff = _now() - datetime.timedelta(hours=1)
    return (
        await session.execute(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.user_id == user_id)
            .where(AnalyticsEvent.occurred_at >= cutoff)
        )
    ).scalar_one()


@router.post("/events", response_model=EventBatchResult)
async def post_events(
    body: EventBatch,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if await _user_event_count_last_hour(session, user.user_id) >= EVENTS_PER_HOUR:
        return JSONResponse(
            status_code=429,
            content={"code": "RATE_LIMIT_REACHED"},
            headers={"Retry-After": "3600"},
        )

    accepted = 0
    rows: list[AnalyticsEvent] = []
    for ev in body.events:
        spec = REGISTRY.get(ev.name)
        if spec is None:
            DROP_COUNTER["unknown_name"] += 1
            continue
        if spec.server_only:
            # The client may not assert a server-known fact (funnel truth).
            DROP_COUNTER["server_only"] += 1
            continue
        if spec.not_yet_live:
            DROP_COUNTER["not_yet_live"] += 1
            continue
        try:
            props = validate_event(ev.name, ev.properties)
        except EventValidationError:
            DROP_COUNTER["invalid"] += 1
            continue
        rows.append(
            AnalyticsEvent(
                event_name=ev.name,
                user_id=user.user_id,
                case_file_id=ev.case_file_id,
                properties=props,
            )
        )
        accepted += 1

    if rows:
        session.add_all(rows)
        await session.commit()

    return EventBatchResult(accepted=accepted, dropped=len(body.events) - accepted)
