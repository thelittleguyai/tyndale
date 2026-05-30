"""Phase CO-2A — cms_ingestion_state table for NCD/LCD incremental ingestion.

One row per source ('ncd', 'lcd_ca', …) tracking last-indexed-at so the weekly
cron only ingests new/changed CMS policies. The policy chunks themselves live in
Qdrant (payer_policies), not Postgres — this is the only schema change for CO-2A.

Revision ID: 0008
Revises:     0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Alembic identifiers
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cms_ingestion_state",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("last_indexed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_successful_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "policies_indexed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        "idx_cms_ingestion_state_last_indexed", "cms_ingestion_state", ["last_indexed_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_cms_ingestion_state_last_indexed", table_name="cms_ingestion_state")
    op.drop_table("cms_ingestion_state")
