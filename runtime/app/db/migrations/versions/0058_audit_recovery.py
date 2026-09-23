"""The §10.4 promise, kept — automatic recovery of system_error audits (e2e re-test 2026-09-23,
item 3).

"Give it another moment, or I'll email you the moment I've got it working again" rendered on
every system_error, and nothing ever re-ran a system_error audit — the recovery email existed
(0040) but its trigger could not fire. The audit_retry cron now re-runs them, bounded:

  * ``recovery_attempts``    — automatic re-runs spent on the current failure (reset when the
                               case reaches a real terminal again)
  * ``recovery_retry_after`` — the next re-run is not due before this (backoff + claim lease)

Chains onto 0057.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_files",
        sa.Column("recovery_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "case_files", sa.Column("recovery_retry_after", sa.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("case_files", "recovery_retry_after")
    op.drop_column("case_files", "recovery_attempts")
