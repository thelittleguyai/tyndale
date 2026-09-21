"""case_files: audit heartbeat + reconcile claim columns (deep review C2, 2026-09-18).

audit_heartbeat_at — bumped by the orchestrator at running + every phase boundary; the
healer measures staleness against it. reconcile_token / reconcile_claimed_at /
reconcile_attempts — the healer's per-row claim, so its terminal write is a compare-and-swap
and a heal that died mid-side-effects is re-pickable. Chains onto 0050.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_files", sa.Column("audit_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "case_files",
        sa.Column("reconcile_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("case_files", sa.Column("reconcile_token", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("case_files", sa.Column("reconcile_claimed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("case_files", "reconcile_claimed_at")
    op.drop_column("case_files", "reconcile_token")
    op.drop_column("case_files", "reconcile_attempts")
    op.drop_column("case_files", "audit_heartbeat_at")
