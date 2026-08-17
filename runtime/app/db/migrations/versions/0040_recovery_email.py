"""add case_files.recovery_email_sent_at

§10.4's recovery notice (2026-08-17): "I'll email you the moment I've got it working again"
becomes a real email when a system_error case subsequently completes. Same exactly-once
discipline as 0038 — stamped only after the provider accepts, NULL retries.

Chains onto 0039.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_files",
        sa.Column("recovery_email_sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_files", "recovery_email_sent_at")
