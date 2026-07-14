"""add message kind + payload for chat-first typed thread entries

Chat-first audit flow, Phase A (Brock 2026-07-10, DL-91). The event bridge persists typed thread
entries (status_card_update / system_message / moment_card / verification_request) as role='system'
messages. Add a `kind` discriminator (default 'message' so every existing row stays a classic turn)
+ a `payload` JSONB for the structured card data. Both additive; no backfill needed.

Chains onto 0029.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

_KIND_CHECK = (
    "kind IN ('message', 'status_card_update', 'system_message', 'moment_card', "
    "'verification_request')"
)


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("kind", sa.Text(), nullable=False, server_default="message"),
    )
    op.add_column("messages", sa.Column("payload", JSONB(), nullable=True))
    op.create_check_constraint("ck_messages_kind", "messages", _KIND_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.drop_column("messages", "payload")
    op.drop_column("messages", "kind")
