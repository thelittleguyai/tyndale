"""Phase CO-6A — admin_verdicts table (Brock's case-review verdict capture).

Fresh table, no backfill needed (DL-66 — nothing pre-existing to migrate).

Revision ID: 0010
Revises:     0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_verdicts",
        sa.Column(
            "verdict_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("target_findings", postgresql.JSONB(), nullable=True),
        sa.Column("target_response", sa.Text(), nullable=True),
        sa.Column(
            "captured_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("verdict_id"),
        sa.ForeignKeyConstraint(
            ["case_file_id"], ["case_files.case_file_id"], name="fk_admin_verdicts_case_file"
        ),
        sa.ForeignKeyConstraint(
            ["admin_user_id"], ["users.user_id"], name="fk_admin_verdicts_admin_user"
        ),
        sa.CheckConstraint(
            "verdict IN ('correct', 'partially_correct', 'wrong')",
            name="ck_admin_verdicts_verdict",
        ),
    )
    op.create_index("idx_admin_verdicts_case_file", "admin_verdicts", ["case_file_id"])
    op.create_index("idx_admin_verdicts_captured_at", "admin_verdicts", ["captured_at"])
    op.create_index("idx_admin_verdicts_admin_user", "admin_verdicts", ["admin_user_id"])


def downgrade() -> None:
    op.drop_index("idx_admin_verdicts_admin_user", table_name="admin_verdicts")
    op.drop_index("idx_admin_verdicts_captured_at", table_name="admin_verdicts")
    op.drop_index("idx_admin_verdicts_case_file", table_name="admin_verdicts")
    op.drop_table("admin_verdicts")
