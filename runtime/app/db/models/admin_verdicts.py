"""AdminVerdict model — Brock's case-review verdicts (Phase CO-6A).

Captured from the admin console (admin.tyndaleapp.net). One row per verdict; a
case can have many. target_findings / target_response scope a verdict to part of
a case (null = whole case / latest response). CO-6B (Sprint D) reads these to
drive chat-driven corrections — CO-6A only captures them.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminVerdict(Base):
    __tablename__ = "admin_verdicts"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('correct', 'partially_correct', 'wrong', 'missed_finding', "
            "'hallucinated', 'partial', 'unable_to_verify')",
            name="ck_admin_verdicts_verdict",
        ),
        Index("idx_admin_verdicts_case_file", "case_file_id"),
        Index("idx_admin_verdicts_captured_at", "captured_at"),
        Index("idx_admin_verdicts_admin_user", "admin_user_id"),
    )

    verdict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=False
    )
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_findings: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # null = whole case
    target_response: Mapped[str | None] = mapped_column(Text, nullable=True)  # null = latest
    # CO-9 Module 3 verdict v2 — descriptors for the missed_finding / hallucinated verdicts.
    missed_findings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    hallucinated_claims: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    captured_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
