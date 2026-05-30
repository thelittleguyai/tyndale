"""CmsIngestionState — last-indexed bookkeeping for the CMS NCD/LCD pipeline.

One row per source ('ncd', 'lcd_ca', 'lcd_ny', …). The incremental cron reads
last_indexed_at to diff the MCD index and ingest only new/changed policies, then
writes the run result back. The policy chunks themselves live in Qdrant
(payer_policies collection), NOT Postgres — this table is pure ingestion state.
"""

from __future__ import annotations

import datetime

from sqlalchemy import TIMESTAMP, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CmsIngestionState(Base):
    __tablename__ = "cms_ingestion_state"
    __table_args__ = (Index("idx_cms_ingestion_state_last_indexed", "last_indexed_at"),)

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 'ncd', 'lcd_ca', …
    last_indexed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    last_successful_run_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    policies_indexed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
