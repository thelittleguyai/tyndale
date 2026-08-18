"""add users.state + optional mailing address

Settings item 2 (2026-08-19): state of residence is the load-bearing jurisdiction field
for seed-era state-law selection (DL-81); address lines are optional context. Per-case
document evidence wins over the profile default (the jurisdiction helper logs conflicts).

Chains onto 0042.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("state", sa.String(2), nullable=True))
    op.add_column("users", sa.Column("address_line1", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("address_line2", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("city", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("zip_code", sa.String(10), nullable=True))


def downgrade() -> None:
    for col in ("zip_code", "city", "address_line2", "address_line1", "state"):
        op.drop_column("users", col)
