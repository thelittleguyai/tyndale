"""Add user_type column to users.

Adds a ``user_type`` text column constrained to {'user', 'admin'}, defaulted
to 'user' so existing rows backfill non-destructively. Phase 2K real-auth
wiring uses this column to gate admin-only routes once Google sign-in lands.

Revision ID: 0002_add_user_type
Revises:     0001_initial
"""

from __future__ import annotations

from alembic import op

# Alembic identifiers
revision = "0002_add_user_type"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent ADD COLUMN with a server default so re-runs on a partially
    # migrated DB don't break. CheckConstraint enforces the allowed values.
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type text NOT NULL DEFAULT 'user'"
    )
    op.create_check_constraint(
        "ck_users_user_type",
        "users",
        "user_type IN ('user', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_user_type", "users", type_="check")
    op.drop_column("users", "user_type")
