"""add case_files.audit_ready_email_sent_at

The audit-ready email (D3, 2026-08-12). Brock's §2.2 promises "I'll email you the moment
it's ready"; this column is the per-case idempotency stamp that makes it exactly-once.

Written only after the provider accepts the message — a failed send leaves NULL so the next
terminal transition retries, rather than the case being marked done with nothing delivered
(the failure mode the nudge ledger had).

Chains onto 0037.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_files",
        sa.Column("audit_ready_email_sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_files", "audit_ready_email_sent_at")
