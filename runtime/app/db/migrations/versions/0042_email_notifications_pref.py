"""add users.email_notifications_enabled

The settings Notifications section stops lying (2026-08-19): SendGrid is live, so the
"coming soon" stub becomes a real per-user preference. Default TRUE (opt-out model — the
nudges are part of the product's promise until the user says otherwise). Gates REMINDERS
only; transactional mail never consults it (see app/notify/email.py for the split).

Chains onto 0041.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "email_notifications_enabled")
