"""add 'awaiting_eob_confirmation' to the case_files status enum

Sprint D (DL-86): the universal EOB-completeness confirmation gate. A case parks in
``awaiting_eob_confirmation`` while Tyndale asks "does that look like all of them?"
before treating the accumulator totals as complete.

Chains onto 0020.
"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_NEW = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'awaiting_eob_confirmation', 'audit_running', "
    "'audit_complete', 'resolved', 'archived')"
)
_OLD = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'audit_running', 'audit_complete', "
    "'resolved', 'archived')"
)


def upgrade() -> None:
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _NEW)


def downgrade() -> None:
    # Park any awaiting_eob_confirmation cases back to a valid old status first.
    op.execute(
        "UPDATE case_files SET status = 'encounter_verified' "
        "WHERE status = 'awaiting_eob_confirmation'"
    )
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _OLD)
