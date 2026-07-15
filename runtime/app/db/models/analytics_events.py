"""AnalyticsEvent — the single, append-only, PHI-free event stream (Internal Analytics P0).

One table for every event (Rule 2). `properties` is validated against the per-event schema in
``app.analytics.events`` before any write — enums / numbers / booleans only, never free text.
Append-only: no updated_at, never mutated. `dedupe_key` (nullable, unique) makes selected writes
idempotent — e.g. an outcome report keys on the case so a double-tapped button can't double-count
(Postgres treats multiple NULLs as distinct, so non-idempotent events are unaffected).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        # Every panel filters by event over a time range; user/case are the join axes.
        Index("idx_analytics_events_name_time", "event_name", "occurred_at"),
        Index("idx_analytics_events_user", "user_id"),
        Index("idx_analytics_events_case", "case_file_id"),
        # Idempotency: at most one row per non-null dedupe_key.
        Index("uq_analytics_events_dedupe", "dedupe_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    case_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Validated against the per-event schema (enums/numbers/booleans only). Never free text.
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)
