"""messages.suggested_replies — tap-to-reply chips on freeform assistant turns

Brock's 2026-08-22 field test, item 3: an assistant turn may carry up to four short
quick replies (parsed + stripped from the model's trailing SUGGESTED line). Stored on
the row so a reloaded conversation renders the same chips under its newest turn.

Chains onto 0045.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("suggested_replies", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "suggested_replies")
