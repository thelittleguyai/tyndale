"""CaseFile model — matches docs/integration-contracts.md Section 2.3.

Includes the `research_log` JSONB field (Change Order 001 item 4) and a `version`
column for optimistic locking (enforcement wires into the write paths in Phase 2).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CaseFile(Base):
    __tablename__ = "case_files"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'encounter_verification_pending', "
            "'encounter_verified', 'audit_running', 'audit_complete', "
            "'resolved', 'archived')",
            name="ck_case_files_status",
        ),
    )

    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    # Documents uploaded for this case (bills, EOBs, insurance card, plan summary).
    documents: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Structured coverage — matches the FHIR Coverage return shape (source-agnostic).
    coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Structured EOB data — same shape as fhir_get_eobs return.
    eobs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Lead Planner plan-to-memory (current plan + version history).
    plan_current: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    plan_history: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # research_log per Change Order 001 item 4. Each entry:
    # {timestamp, topic, what_was_checked, result_summary, finding_id|null}
    research_log: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Phase 2I encounter verification — Bill Detective's plain-language line-item
    # translations (each a LineItem dict; see app/schemas/encounter.py).
    line_items: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # The user's per-line-item confirmations (each a LineItemConfirmation dict).
    encounter_confirmations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Optimistic locking counter.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
