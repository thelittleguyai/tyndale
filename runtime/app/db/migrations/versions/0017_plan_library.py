"""plan_library — plan-level benefit designs (Phase CO-12C, DL-73)

Plan-level ONLY: keyed by (payer, plan_id/name, plan_year); ``benefit_design`` holds
benefit terms (deductible / coinsurance / OOP / copays) with NO PHI / user
identifiers (stripped before write — app/services/plan_library.py). A confirm
increments ``confidence``; a reject forks a new row, so the (payer, plan, year) key
is intentionally NOT unique. New table -> no DL-66 backfill. Chains onto 0016.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_library",
        sa.Column(
            "plan_library_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("payer", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=True),
        sa.Column("plan_name", sa.Text(), nullable=True),
        sa.Column("plan_year", sa.Integer(), nullable=False),
        sa.Column(
            "benefit_design",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'user_confirmed'"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("plan_library_id"),
    )
    op.create_index("idx_plan_library_match", "plan_library", ["payer", "plan_year"])


def downgrade() -> None:
    op.drop_index("idx_plan_library_match", table_name="plan_library")
    op.drop_table("plan_library")
