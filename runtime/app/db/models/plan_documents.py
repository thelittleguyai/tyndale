"""PlanDocument — the PLAN-level document home (2026-08-19, settings item 5).

An SBC describes the user's PLAN, not one bill — so it lives at the user level,
uploaded once, and satisfies the SBC line on EVERY case's needs/unlock-more
checklist (the resolver checks here before asking per-case). ``coverage`` keeps
the high-confidence SBC term extraction (deductible_amount / oop_max_amount /
coinsurance_percent / copays — DL-54: plan terms + code-free labels only), which
feeds rung-2 as the fallback when a case has no coverage of its own. The file
bytes live in Azure Blob (``blob_ref``), never in Postgres.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlanDocument(Base):
    __tablename__ = "plan_documents"

    plan_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )
    # Classifier verdict ('plan_summary' is the SBC family; an off-family upload is
    # still stored — the user chose to file it here — but doesn't satisfy checklists).
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    blob_ref: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # High-confidence SBC plan terms (empty dict when extraction read nothing).
    coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ocr_text_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
