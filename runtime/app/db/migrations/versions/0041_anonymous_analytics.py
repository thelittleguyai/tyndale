"""analytics_events.user_id nullable — the anonymous path for access_request_received

The statutory access-request intake is deliberately unauthenticated, so its registered
analytics event had nowhere to land while user_id was NOT NULL. Nullable now; the emit layer
allowlists exactly which events may omit the user (only access_request_received), so this
does not open an anonymous door for anything else.

Chains onto 0040.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("analytics_events", "user_id", existing_type=sa.dialects.postgresql.UUID(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM analytics_events WHERE user_id IS NULL")
    op.alter_column("analytics_events", "user_id", existing_type=sa.dialects.postgresql.UUID(), nullable=False)
