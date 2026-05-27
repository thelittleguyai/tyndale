"""Finding model — matches docs/integration-contracts.md Section 2.3."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("voice_tier IN ('A', 'B', 'C')", name="ck_findings_voice_tier"),
        Index("idx_findings_case_file", "case_file_id"),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=False
    )
    finding_type: Mapped[str] = mapped_column(Text, nullable=False)  # payer_side | provider_side | encounter_mismatch
    category: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. bundling, cost_sharing_miscalculation
    subagent_source: Mapped[str] = mapped_column(Text, nullable=False)
    voice_tier: Mapped[str] = mapped_column(Text, nullable=False)  # A | B | C
    facts: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Tier A structured facts
    legal_claim: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Tier B claim + citation
    recommendation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Tier C action + reasoning
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
