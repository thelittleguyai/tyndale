"""Phase CO-1A — guided-intake columns on case_files.

Adds intake_status / intake_current_step / visit_context + an index. Existing
case files (created before the wizard existed and already carrying data) are
backfilled to intake_status='complete' so pre-CO-1A users are NOT re-routed
through the new wizard; only NEW case files default to 'not_started'.

Revision ID: 0009
Revises:     0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Alembic identifiers
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_files",
        sa.Column("intake_status", sa.Text(), nullable=False, server_default="not_started"),
    )
    op.add_column("case_files", sa.Column("intake_current_step", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("visit_context", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_case_files_intake_status",
        "case_files",
        "intake_status IN ('not_started', 'in_progress', 'complete')",
    )
    op.create_index("idx_case_files_intake_status", "case_files", ["intake_status"])
    # Don't re-onboard users who already have case files: treat all pre-existing
    # rows as complete. (New rows inserted after this migration get the column
    # default 'not_started'.)
    op.execute(
        "UPDATE case_files SET intake_status = 'complete' WHERE intake_status = 'not_started'"
    )


def downgrade() -> None:
    op.drop_index("idx_case_files_intake_status", table_name="case_files")
    op.drop_constraint("ck_case_files_intake_status", "case_files", type_="check")
    op.drop_column("case_files", "visit_context")
    op.drop_column("case_files", "intake_current_step")
    op.drop_column("case_files", "intake_status")
