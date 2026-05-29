"""Add user_type column to users.

Adds a ``user_type`` text column constrained to {'user', 'admin'}, defaulted
to 'user' so existing rows backfill non-destructively. Phase 2K real-auth
wiring uses this column to gate admin-only routes once Google sign-in lands.

Revision ID: 0002
Revises:     0001
"""

from __future__ import annotations

from alembic import op

# Alembic identifiers — match the bare-number style 0001_initial.py declared
# (its revision = "0001"). File name and revision ID are independent in Alembic;
# the ID is what's stored in alembic_version + threaded into the dep chain.
revision = "0002"
down_revision = "0001"
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
