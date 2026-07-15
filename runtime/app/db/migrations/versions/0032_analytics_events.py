"""create analytics_events — the PHI-free internal-analytics event stream

Internal Analytics P0 (Brock's dashboard spec 2026-07-11). One append-only table for every event
(Rule 2); properties are validated against a per-event schema (enums/numbers/booleans only) before
any write, so no free text ever lands. Indexed for the dashboard's access paths; a nullable-unique
dedupe_key makes selected writes (e.g. outcome reports) idempotent.

Chains onto 0031.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at", sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"), nullable=False,
        ),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "properties", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_analytics_events_name_time", "analytics_events", ["event_name", "occurred_at"]
    )
    op.create_index("idx_analytics_events_user", "analytics_events", ["user_id"])
    op.create_index("idx_analytics_events_case", "analytics_events", ["case_file_id"])
    op.create_index(
        "uq_analytics_events_dedupe", "analytics_events", ["dedupe_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_analytics_events_dedupe", table_name="analytics_events")
    op.drop_index("idx_analytics_events_case", table_name="analytics_events")
    op.drop_index("idx_analytics_events_user", table_name="analytics_events")
    op.drop_index("idx_analytics_events_name_time", table_name="analytics_events")
    op.drop_table("analytics_events")
