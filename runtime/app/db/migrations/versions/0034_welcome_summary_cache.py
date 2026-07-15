"""add users.welcome_summary_cache

Dashboard welcome-summary guardrails (2026-07-15). Persist the generated summary keyed on a hash of
the case-state snapshot so it regenerates ONLY when the user's cases change — same words on every
load until state changes, instead of a fresh (and drift-prone) generation each time.

Chains onto 0033.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("welcome_summary_cache", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "welcome_summary_cache")
