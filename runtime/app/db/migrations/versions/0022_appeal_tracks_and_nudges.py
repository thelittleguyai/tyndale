"""appeal_tracks table + case_files.nudges_sent

Sprint G (shadow-mode DL-55/56): the escalation-ladder state persisted per case, plus the
per-case nudge idempotency ledger. Appeals stay dark (ENABLE_APPEALS_CASEMGMT=false) — this
migration lands the schema only.

Chains onto 0021.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_STATE_CHECK = (
    "current_state IN ('call', 'supervisor', 'internal_appeal', "
    "'external_review', 'cms_or_state_complaint')"
)


def upgrade() -> None:
    op.create_table(
        "appeal_tracks",
        sa.Column(
            "appeal_track_id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_file_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("case_files.case_file_id"), nullable=False,
        ),
        sa.Column("current_state", sa.Text(), nullable=False, server_default=sa.text("'call'")),
        sa.Column("history", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_STATE_CHECK, name="ck_appeal_tracks_state"),
    )
    op.create_index("idx_appeal_tracks_case_file_id", "appeal_tracks", ["case_file_id"])

    op.add_column(
        "case_files",
        sa.Column("nudges_sent", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("case_files", "nudges_sent")
    op.drop_index("idx_appeal_tracks_case_file_id", table_name="appeal_tracks")
    op.drop_table("appeal_tracks")
