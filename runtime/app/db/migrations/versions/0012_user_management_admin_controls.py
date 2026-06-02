"""Phase CO-9 — user management: block, soft-delete, JWT versioning.

Net-new columns on users. Per DL-66 the column defaults ARE the backfill: every existing
row gets is_blocked=FALSE and jwt_version=1 from the server_defaults; the nullable
timestamp/actor columns are correctly NULL for users with no admin action yet.

Revision ID: 0012
Revises:     0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("blocked_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("users", sa.Column("blocked_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("blocked_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("soft_deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("soft_deleted_by", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("jwt_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "users", sa.Column("last_admin_action_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_users_blocked_by", "users", "users", ["blocked_by"], ["user_id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_users_soft_deleted_by",
        "users",
        "users",
        ["soft_deleted_by"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_users_is_blocked",
        "users",
        ["is_blocked"],
        postgresql_where=sa.text("is_blocked = TRUE"),
    )
    op.create_index("idx_users_soft_deleted_at", "users", ["soft_deleted_at"])


def downgrade() -> None:
    op.drop_index("idx_users_soft_deleted_at", table_name="users")
    op.drop_index("idx_users_is_blocked", table_name="users")
    op.drop_constraint("fk_users_soft_deleted_by", "users", type_="foreignkey")
    op.drop_constraint("fk_users_blocked_by", "users", type_="foreignkey")
    for col in (
        "last_admin_action_at",
        "jwt_version",
        "soft_deleted_by",
        "soft_deleted_at",
        "blocked_reason",
        "blocked_by",
        "blocked_at",
        "is_blocked",
    ):
        op.drop_column("users", col)
