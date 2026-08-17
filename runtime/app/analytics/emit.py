"""Server-side event emission (Rule 3 — funnel truth is server-known).

``emit`` and ``emit_idempotent`` are best-effort and NEVER raise into the product path: a
validation failure or a DB error is logged and swallowed (analytics durability must not be
coupled to a user's audit succeeding). Each write runs in its OWN session so a constraint
violation can't poison the caller's transaction.

``emit_idempotent`` sets ``dedupe_key`` and does INSERT … ON CONFLICT DO NOTHING, so a path that
can legitimately fire twice (a double-tapped outcome button) records exactly one row. This is the
P0 reliability guarantee Brock called out for the outcome-capture path.
"""

from __future__ import annotations

import datetime
import uuid
from collections import Counter

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.analytics.events import EventValidationError, validate_event
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent

log = structlog.get_logger(__name__)

# Why events were dropped, since boot — surfaced on the ops panel so silent loss is visible.
# Keys: 'invalid' (schema mismatch), 'unknown_name', 'server_only' (client tried a server event),
# 'write_error'.
DROP_COUNTER: Counter[str] = Counter()


def get_drop_counts() -> dict[str, int]:
    return dict(DROP_COUNTER)


# The ONLY events that may be written without a user — the unauthenticated statutory intake.
# Everything else arriving with user_id=None is dropped and counted: anonymity is a property
# of one named surface, not an option.
ANONYMOUS_EVENTS: frozenset[str] = frozenset({"access_request_received"})


async def emit(
    event_name: str,
    *,
    user_id: uuid.UUID | None,
    case_file_id: uuid.UUID | None = None,
    properties: dict | None = None,
    occurred_at: datetime.datetime | None = None,
) -> bool:
    """Validate + append one event. Returns True on write, False on any drop (never raises)."""
    if user_id is None and event_name not in ANONYMOUS_EVENTS:
        DROP_COUNTER["anonymous_not_allowed"] += 1
        log.warning("analytics.emit.anonymous_not_allowed", event_name=event_name)
        return False
    try:
        props = validate_event(event_name, properties)
    except EventValidationError as e:
        DROP_COUNTER["invalid"] += 1
        log.warning("analytics.emit.invalid", event_name=event_name, error=str(e))
        return False
    try:
        async with AsyncSessionLocal() as s:
            s.add(
                AnalyticsEvent(
                    event_name=event_name,
                    user_id=user_id,
                    case_file_id=case_file_id,
                    properties=props,
                    occurred_at=occurred_at,
                )
            )
            await s.commit()
        return True
    except Exception as e:  # noqa: BLE001 — analytics is best-effort; never break the product path
        DROP_COUNTER["write_error"] += 1
        log.warning("analytics.emit.failed", event_name=event_name, error=str(e))
        return False


async def emit_idempotent(
    event_name: str,
    *,
    dedupe_key: str,
    user_id: uuid.UUID,
    case_file_id: uuid.UUID | None = None,
    properties: dict | None = None,
) -> bool:
    """Append at most one event per ``dedupe_key`` (ON CONFLICT DO NOTHING). Returns True if the
    write executed without error (whether or not it was a fresh insert)."""
    try:
        props = validate_event(event_name, properties)
    except EventValidationError as e:
        DROP_COUNTER["invalid"] += 1
        log.warning("analytics.emit.invalid", event_name=event_name, error=str(e))
        return False
    try:
        async with AsyncSessionLocal() as s:
            stmt = (
                pg_insert(AnalyticsEvent.__table__)
                .values(
                    event_name=event_name,
                    user_id=user_id,
                    case_file_id=case_file_id,
                    properties=props,
                    dedupe_key=dedupe_key,
                )
                .on_conflict_do_nothing(index_elements=["dedupe_key"])
            )
            await s.execute(stmt)
            await s.commit()
        return True
    except Exception as e:  # noqa: BLE001
        DROP_COUNTER["write_error"] += 1
        log.warning("analytics.emit_idempotent.failed", event_name=event_name, error=str(e))
        return False
