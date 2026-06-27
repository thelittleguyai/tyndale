"""InsuranceInfo — one IDENTIFIED row per user (CO-17, DL-78).

The structured insurance-card data, keyed 1:1 to the user (UNIQUE user_id). This is
USER-IDENTIFIED (member id, names, DOBs) and is kept SEPARATE from plan_library, which
holds only the PHI-stripped plan-level design (DL-73). The card IMAGES live in
insurance_cards (Azure Blob), never here.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InsuranceInfo(Base):
    __tablename__ = "insurance_info"
    __table_args__ = (UniqueConstraint("user_id", name="uq_insurance_info_user"),)

    insurance_info_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    insurer: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_id_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_id_suffix: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_birth_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    member_gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_employer: Mapped[str | None] = mapped_column(Text, nullable=True)
    payer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payer_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    payer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    rx_bin: Mapped[str | None] = mapped_column(Text, nullable=True)
    rx_pcn: Mapped[str | None] = mapped_column(Text, nullable=True)
    rx_grp: Mapped[str | None] = mapped_column(Text, nullable=True)
    rx_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    rx_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    pbm: Mapped[str | None] = mapped_column(Text, nullable=True)
    medicare_medicaid_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    medicare_part_a_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    medicare_part_b_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    copays: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    dependents: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_extracted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
