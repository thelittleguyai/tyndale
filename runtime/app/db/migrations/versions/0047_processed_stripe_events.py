"""processed_stripe_events — Stripe webhook idempotency ledger (audit 2026-08-27 item 6).

Stripe redelivers webhooks on any slow response; without an event-id ledger a redelivered
subscription event re-applies state. Chains onto 0046.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_stripe_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("processed_stripe_events")
