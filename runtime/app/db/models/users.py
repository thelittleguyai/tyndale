"""User model.

Not fully specified in the integration contracts (which reference users(user_id));
kept minimal here. Captures the two-consent model from L05 (service vs improvement).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, Boolean, CheckConstraint, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("user_type IN ('user', 'admin')", name="ck_users_user_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 'user' (default) | 'admin'. Phase 2K real-auth checks this to gate
    # admin-only routes (e.g., a future case-triage console).
    user_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'user'")
    )
    # Consent model per docs/tyndale-spec/L05_feedback_consent_schema.md
    service_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    improvement_consent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
