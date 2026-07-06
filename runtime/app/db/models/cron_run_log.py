"""cron_run_log model (Phase CO-9) — every cron run, scheduled or admin-triggered.

Powers the admin system-health cron control (Module 5): list crons, trigger one
manually (triggered_source='manual_admin'), and browse run history.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CronRunLog(Base):
    __tablename__ = "cron_run_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial', 'interrupted')",
            name="ck_cron_run_log_status",
        ),
        CheckConstraint(
            "triggered_source IN ('scheduled', 'manual_admin', 'manual_cli')",
            name="ck_cron_run_log_triggered_source",
        ),
        Index("idx_cron_run_log_cron_name_started", "cron_name", text("started_at DESC")),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cron_name: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    triggered_source: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
