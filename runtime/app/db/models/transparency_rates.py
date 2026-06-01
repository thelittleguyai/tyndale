"""transparency_rates — structured price data for cost estimation (Phase CO-3A).

One row per (source, code, payer/hospital, location, rate_type). Sources:
medicare_pfs (baseline allowable), hospital_mrf (negotiated), tic_mrf (negotiated),
trilliant (stub, DL-50). New sources land in transparency_rates_staging first
(DL-59 — ≥90% extraction-confidence sample before promotion to live).

location_zip3 is the 3-digit ZIP only (HIPAA Safe Harbor). confidence_score is the
DL-63 weighted score (Medicare baseline = 1.0).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, Index, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_SOURCE_CHECK = "source IN ('medicare_pfs', 'hospital_mrf', 'tic_mrf', 'trilliant')"


class _RateColumns:
    """Shared column set for the live + staging tables (DL-59)."""

    rate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)  # HCPCS/CPT/DRG
    code_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    payer: Mapped[str | None] = mapped_column(Text, nullable=True)  # null for medicare_pfs
    hospital_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # CMS provider number
    location_zip3: Mapped[str | None] = mapped_column(Text, nullable=True)  # HIPAA Safe Harbor
    rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    rate_type: Mapped[str] = mapped_column(Text, nullable=False)
    effective_year: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    ingestion_timestamp: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TransparencyRate(Base, _RateColumns):
    __tablename__ = "transparency_rates"
    __table_args__ = (
        CheckConstraint(_SOURCE_CHECK, name="ck_transparency_rates_source"),
        Index("idx_transparency_rates_code", "code"),
        Index("idx_transparency_rates_code_location", "code", "location_zip3"),
        Index("idx_transparency_rates_payer", "payer", postgresql_where=text("payer IS NOT NULL")),
        Index("idx_transparency_rates_source", "source"),
    )


class TransparencyRateStaging(Base, _RateColumns):
    """New-source landing zone (DL-59). Promotion to live = ≥90% sample pass."""

    __tablename__ = "transparency_rates_staging"
    __table_args__ = (
        CheckConstraint(_SOURCE_CHECK, name="ck_transparency_rates_staging_source"),
        Index("idx_transparency_rates_staging_code", "code"),
    )
