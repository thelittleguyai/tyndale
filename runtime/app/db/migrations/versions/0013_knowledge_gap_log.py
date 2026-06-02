"""Phase CO-9 — knowledge_gap_log: subagents record where data was missing/weak.

Fresh table, no backfill (DL-66). The `case_id` column references case_files' real PK
(case_file_id). Feeds the admin "what to ingest next" dashboard (Module 6).

Revision ID: 0013
Revises:     0012
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_gap_log",
        sa.Column(
            "gap_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("gap_type", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "logged_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_by_source", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("gap_id"),
        sa.CheckConstraint(
            "gap_type IN ('no_data', 'low_confidence', 'self_reported')",
            name="ck_knowledge_gap_log_gap_type",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["case_files.case_file_id"], name="fk_knowledge_gap_log_case"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_knowledge_gap_log_user"),
    )
    op.create_index(
        "idx_knowledge_gap_log_logged_at", "knowledge_gap_log", [sa.text("logged_at DESC")]
    )
    op.create_index(
        "idx_knowledge_gap_log_agent_gap_type", "knowledge_gap_log", ["agent_name", "gap_type"]
    )
    op.create_index(
        "idx_knowledge_gap_log_unresolved",
        "knowledge_gap_log",
        [sa.text("logged_at DESC")],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_gap_log_unresolved", table_name="knowledge_gap_log")
    op.drop_index("idx_knowledge_gap_log_agent_gap_type", table_name="knowledge_gap_log")
    op.drop_index("idx_knowledge_gap_log_logged_at", table_name="knowledge_gap_log")
    op.drop_table("knowledge_gap_log")
