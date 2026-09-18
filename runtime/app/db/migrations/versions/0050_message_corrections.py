"""messages.corrected_by_message_id / corrects_message_id — Human Review §7-2f (2026-09-18).

Design-toward Phase 3 user-facing corrections: a corrected message points at its append-only
follow-up and the follow-up points back. Read-model only in Phase 1. Chains onto 0049.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("corrected_by_message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("messages.message_id"), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("corrects_message_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("messages.message_id"), nullable=True),
    )
    op.create_index("idx_messages_corrects", "messages", ["corrects_message_id"])


def downgrade() -> None:
    op.drop_index("idx_messages_corrects", table_name="messages")
    op.drop_column("messages", "corrects_message_id")
    op.drop_column("messages", "corrected_by_message_id")
