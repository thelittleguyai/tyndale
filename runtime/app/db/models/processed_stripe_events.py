"""Stripe webhook idempotency ledger (audit 2026-08-27 item 6): one row per processed
event id. Stripe retries webhooks aggressively; INSERT … ON CONFLICT DO NOTHING on this
table is what makes a redelivered event a no-op instead of a re-applied state change."""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedStripeEvent(Base):
    __tablename__ = "processed_stripe_events"

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    processed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
