"""A summary the provider could not write in time is PENDING, not a failed audit — e2e
re-test 2026-09-23, item 1.

The specimen run persisted three findings and the three numbers, then one Foundry 429 on the
Lead Planner's summary call ended it ``system_error``. The summary is optional to the reveal:
the run now finishes ``audit_complete`` with the summary marked pending, and the audit_retry
cron writes it later from the inputs the run saved.

  * ``summary_pending``        — the reveal shipped without its summary; a retry is owed
  * ``summary_inputs``         — what the Lead Planner composes from (Bill Detective's and Math
                                 Person's final text), kept only while pending
  * ``summary_retry_attempts`` — retries spent (bounded; exhausted = give up honestly)
  * ``summary_retry_after``    — the next attempt is not due before this (backoff + claim lease)

Chains onto 0056.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_files",
        sa.Column("summary_pending", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("case_files", sa.Column("summary_inputs", postgresql.JSONB(), nullable=True))
    op.add_column(
        "case_files",
        sa.Column("summary_retry_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "case_files", sa.Column("summary_retry_after", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    # the cron's pickup is "pending and due" — a tiny partial index keeps it off the big table
    op.create_index(
        "ix_case_files_summary_pending_due",
        "case_files",
        ["summary_retry_after"],
        postgresql_where=sa.text("summary_pending"),
    )


def downgrade() -> None:
    op.drop_index("ix_case_files_summary_pending_due", table_name="case_files")
    op.drop_column("case_files", "summary_retry_after")
    op.drop_column("case_files", "summary_retry_attempts")
    op.drop_column("case_files", "summary_inputs")
    op.drop_column("case_files", "summary_pending")
