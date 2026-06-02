"""knowledge_gap_log model (Phase CO-9) — subagent-reported data gaps.

A subagent calls log_knowledge_gap() when it queried the data layer and found nothing
(no_data), found weak hits (low_confidence), or reasoned that it lacks data
(self_reported). Drives the admin "what to ingest next" dashboard (Module 6).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeGapLog(Base):
    __tablename__ = "knowledge_gap_log"
    __table_args__ = (
        CheckConstraint(
            "gap_type IN ('no_data', 'low_confidence', 'self_reported')",
            name="ck_knowledge_gap_log_gap_type",
        ),
        Index("idx_knowledge_gap_log_logged_at", "logged_at"),
        Index("idx_knowledge_gap_log_agent_gap_type", "agent_name", "gap_type"),
    )

    gap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # case_id references case_files' real PK (case_file_id) — the column keeps the
    # prompt-specified name `case_id`.
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    gap_type: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    logged_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    resolved_by_source: Mapped[str | None] = mapped_column(Text, nullable=True)
