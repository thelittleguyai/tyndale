"""create analytics_daily — daily metric rollups (numerator/denominator/definition per Rule 1)

Internal Analytics P0 (§2). Every row pins its definition (a CHECK refuses a blank one), so no
ratio can be stored without naming what it divides by. Unique per (metric_key, day); `backfilled`
separates historical-from-source rows from live-instrumented ones.

Chains onto 0032.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_daily",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("numerator", sa.Float(), nullable=False),
        sa.Column("denominator", sa.Float(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("backfilled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "computed_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint("length(trim(definition)) > 0", name="ck_analytics_daily_definition"),
    )
    op.create_index(
        "uq_analytics_daily_metric_day", "analytics_daily", ["metric_key", "day"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_analytics_daily_metric_day", table_name="analytics_daily")
    op.drop_table("analytics_daily")
