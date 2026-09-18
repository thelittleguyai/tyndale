"""admin_verdicts.cause + structured_note — Human Review §7-2b (2026-09-18).

A disapproval names exactly one cause (content_gap | reasoning_error | bad_input |
stale_data_source) and carries the three-prompt structured note. Existing rows null.
Chains onto 0048.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_verdicts", sa.Column("cause", sa.Text(), nullable=True))
    op.add_column("admin_verdicts", sa.Column("structured_note", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_admin_verdicts_cause",
        "admin_verdicts",
        "cause IS NULL OR cause IN ('content_gap', 'reasoning_error', 'bad_input', "
        "'stale_data_source')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_admin_verdicts_cause", "admin_verdicts", type_="check")
    op.drop_column("admin_verdicts", "structured_note")
    op.drop_column("admin_verdicts", "cause")
