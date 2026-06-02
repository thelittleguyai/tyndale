"""Phase CO-9 — cron_run_log: every cron run (scheduled or admin-triggered) recorded.

Fresh table, no backfill (DL-66). Powers the admin system-health cron control (Module 5).

Revision ID: 0014
Revises:     0013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cron_run_log",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cron_name", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("triggered_source", sa.Text(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial')",
            name="ck_cron_run_log_status",
        ),
        sa.CheckConstraint(
            "triggered_source IN ('scheduled', 'manual_admin', 'manual_cli')",
            name="ck_cron_run_log_triggered_source",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"], ["users.user_id"], name="fk_cron_run_log_triggered_by"
        ),
    )
    op.create_index(
        "idx_cron_run_log_cron_name_started",
        "cron_run_log",
        ["cron_name", sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_cron_run_log_cron_name_started", table_name="cron_run_log")
    op.drop_table("cron_run_log")
