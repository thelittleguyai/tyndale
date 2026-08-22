"""Message model (Phase CO-10 chat surface).

One row per turn in a conversation. The JSONB columns persist the rich chat
rendering: ``content_chunks`` (the A/B/C tiered sections), ``tool_calls`` (the
subagent tool-call indicators), and ``citations`` (the citation chips, plus the
freeform ``create_case_cta`` action). ``status`` drives the streaming / stopped /
failed UI states.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence_number", name="uq_messages_conv_seq"
        ),
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')", name="ck_messages_role"
        ),
        CheckConstraint(
            "status IN ('streaming', 'complete', 'stopped', 'failed')",
            name="ck_messages_status",
        ),
        CheckConstraint(
            "kind IN ('message', 'status_card_update', 'system_message', 'moment_card', "
            "'verification_request', 'verification_suggestion', 'attest_request')",
            name="ck_messages_kind",
        ),
        Index(
            "idx_messages_conversation_id_sequence",
            "conversation_id",
            "sequence_number",
        ),
        Index(
            "idx_messages_streaming",
            "conversation_id",
            postgresql_where=text("status = 'streaming'"),
        ),
        # Bridge marker idempotency (migration 0039) — the DB half of "one thread entry per
        # marker". Partial: rows without a marker are ordinary messages and free to repeat.
        # Declared here so `alembic check` knows the index is intentional, not drift.
        Index(
            "uq_messages_conversation_marker",
            "conversation_id",
            text("(payload ->> 'marker')"),
            unique=True,
            postgresql_where=text("(payload ->> 'marker') IS NOT NULL"),
        ),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.conversation_id"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # user | assistant | system
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{ tier: 'A'|'B'|'C', text, citations, confidence }]
    content_chunks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{ tool_name, input_summary, output_summary, timestamp, duration_ms, subagent }]
    tool_calls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{ source_id, title, url, snippet, effective_date, payer? }] (+ create_case_cta action)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence_overall: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    # Tap-to-reply chips (Brock 2026-08-22, item 3): ≤4 short strings parsed off the model's
    # trailing SUGGESTED line. Rendered under the NEWEST assistant turn only.
    suggested_replies: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Chat-first typed thread entries (DL-91). `kind` discriminates the render — 'message' is the
    # classic text/chunks turn; the others are bridge-authored (role='system') cards. `payload`
    # carries the structured card data (status bars / verification group / moment card).
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'message'"))
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'complete'")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
