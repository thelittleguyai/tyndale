"""ConsentHistory — audit trail of improvement-consent changes (Phase 2J)."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConsentHistory(Base):
    __tablename__ = "consent_history"
    __table_args__ = (Index("idx_consent_history_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    changed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    from_consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    to_consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
