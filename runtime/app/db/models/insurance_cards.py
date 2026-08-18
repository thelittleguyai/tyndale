"""InsuranceCard — one row per card side (CO-17, DL-78).

The card IMAGE lives in Azure Blob (``blob_ref``); the bytes are NEVER stored base64
in Postgres. UNIQUE(user_id, card_type) — a re-upload REPLACES the same side.
``raw_ocr_json`` keeps the per-side Azure extraction for re-merge / debugging.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InsuranceCard(Base):
    __tablename__ = "insurance_cards"
    __table_args__ = (
        # secondary_front/back joined in 0044 (settings item 4) — the SAME storage and
        # capture path serves the secondary plan's card, keyed by type, no new column.
        CheckConstraint(
            "card_type IN ('front', 'back', 'secondary_front', 'secondary_back')",
            name="ck_insurance_cards_card_type",
        ),
        UniqueConstraint("user_id", "card_type", name="uq_insurance_cards_user_type"),
    )

    insurance_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    card_type: Mapped[str] = mapped_column(Text, nullable=False)
    blob_ref: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_ocr_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
