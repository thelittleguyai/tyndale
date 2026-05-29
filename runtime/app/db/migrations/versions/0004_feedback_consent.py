"""Feedback capture surface — consent_history table + case_files
last_outcome_check_at column (Phase 2J).

- consent_history: an audit trail of improvement-consent changes (for the
  GET /v1/user/me/consent-history compliance endpoint).
- case_files.last_outcome_check_at: set when the user answers/skips an outcome
  follow-up prompt, so the dashboard stops re-prompting.

Revision ID: 0004
Revises:     0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS last_outcome_check_at timestamptz NULL"
    )
    op.create_table(
        "consent_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "changed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("from_consent", sa.Boolean(), nullable=False),
        sa.Column("to_consent", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_consent_history_user"),
    )
    op.create_index("idx_consent_history_user", "consent_history", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_consent_history_user", table_name="consent_history")
    op.drop_table("consent_history")
    op.drop_column("case_files", "last_outcome_check_at")
