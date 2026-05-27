"""Deadline model — matches docs/integration-contracts.md Section 2.3."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Deadline(Base):
    __tablename__ = "deadlines"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'missed')", name="ck_deadlines_status"
        ),
        Index("idx_deadlines_case_file_date", "case_file_id", "deadline_date"),
    )

    deadline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=False
    )
    deadline_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    deadline_type: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. erisa_internal_appeal
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    # which thresholds have been notified (14d/7d/3d/24h)
    notified_thresholds: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
