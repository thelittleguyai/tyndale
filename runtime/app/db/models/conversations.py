"""Conversation model (Phase CO-10 chat surface).

One row per chat thread. ``case_id`` NULL = freeform mode; NOT NULL = per-case
mode (the conversation is scoped to a case file). ``message_count`` +
``last_message_at`` are denormalised so the conversation-list view doesn't have
to aggregate ``messages`` on every load.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_user_id_updated_at", "user_id", text("updated_at DESC")),
        Index(
            "idx_conversations_case_id",
            "case_id",
            postgresql_where=text("case_id IS NOT NULL"),
        ),
        Index(
            "idx_conversations_freeform",
            "user_id",
            text("updated_at DESC"),
            postgresql_where=text("case_id IS NULL AND is_archived = FALSE"),
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    # NULL = freeform mode; NOT NULL = per-case mode.
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_message_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def mode(self) -> str:
        return "freeform" if self.case_id is None else "per_case"
