"""Magic-link single-use tracking (Phase 2K).

Revision ID: 0005
Revises:     0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "magic_link_consumed",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("idx_magic_link_expires", "magic_link_consumed", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_magic_link_expires", table_name="magic_link_consumed")
    op.drop_table("magic_link_consumed")
