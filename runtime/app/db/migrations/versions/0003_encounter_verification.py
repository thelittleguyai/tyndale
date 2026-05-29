"""Encounter verification — expand case_files status set + add line_items /
encounter_confirmations JSONB columns.

The Phase 2I two-phase audit flow (extract -> confirmations -> finalize) needs
new case_files.status values and somewhere to persist the translated line items
+ the user's per-line-item confirmations.

Revision ID: 0003
Revises:     0002
"""

from __future__ import annotations

from alembic import op

# Alembic identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_OLD_STATUSES = "('open', 'in_progress', 'resolved', 'archived')"
_NEW_STATUSES = (
    "('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'audit_running', 'audit_complete', "
    "'resolved', 'archived')"
)


def upgrade() -> None:
    # Expand the status CHECK constraint (drop + recreate).
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint(
        "ck_case_files_status", "case_files", f"status IN {_NEW_STATUSES}"
    )
    # Persist encounter-verification working data.
    op.execute(
        "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS line_items jsonb NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS encounter_confirmations jsonb NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.drop_column("case_files", "encounter_confirmations")
    op.drop_column("case_files", "line_items")
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint(
        "ck_case_files_status", "case_files", f"status IN {_OLD_STATUSES}"
    )
