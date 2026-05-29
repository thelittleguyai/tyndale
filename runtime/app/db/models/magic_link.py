"""MagicLinkConsumed — single-use enforcement for magic-link tokens (Phase 2K).

A row here means the jti has been redeemed. The verify route inserts the jti
on first successful use; a replay finds the existing row and is rejected (401).
Rows past expires_at are cleaned up by a daily cron (Phase 4)."""

from __future__ import annotations

import datetime

from sqlalchemy import TIMESTAMP, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MagicLinkConsumed(Base):
    __tablename__ = "magic_link_consumed"
    __table_args__ = (Index("idx_magic_link_expires", "expires_at"),)

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    consumed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
