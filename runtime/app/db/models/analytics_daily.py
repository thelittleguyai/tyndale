"""AnalyticsDaily — daily metric rollups (Internal Analytics P0).

Rule 1 (every rate names its denominator) is enforced at the storage layer: every row carries the
numerator, the denominator (null only for a pure count), and a NON-EMPTY pinned definition string.
A CHECK constraint refuses a row whose definition is blank, so no ratio can ever be stored without
saying what it divides by. `value` is num/den (null when den is 0 — the dashboard shows the raw
n/d instead of a divide-by-zero). `backfilled` marks rows derived from historical source tables
(cases/findings/feedback) rather than the live event stream.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsDaily(Base):
    __tablename__ = "analytics_daily"
    __table_args__ = (
        # Rule 1: a stored metric must always name what it means — no blank definitions.
        CheckConstraint("length(trim(definition)) > 0", name="ck_analytics_daily_definition"),
        Index("uq_analytics_daily_metric_day", "metric_key", "day", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    numerator: Mapped[float] = mapped_column(Float, nullable=False)
    denominator: Mapped[float | None] = mapped_column(Float, nullable=True)  # null for a pure count
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # null when denominator is 0
    definition: Mapped[str] = mapped_column(Text, nullable=False)  # Rule 1 — never blank
    backfilled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    computed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
