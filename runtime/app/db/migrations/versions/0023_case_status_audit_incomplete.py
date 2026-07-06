"""add 'audit_incomplete' to the case_files status enum

Item 1 (2026-07-06): the audit degrade / wall-clock-budget path marks a case
``audit_incomplete``, but that value was never in the status CHECK constraint — so
_set_status('audit_incomplete') failed on commit and the case was left stuck in
audit_running. Add it.

Chains onto 0022.
"""

from __future__ import annotations

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_NEW = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'awaiting_eob_confirmation', 'audit_running', "
    "'audit_complete', 'audit_incomplete', 'resolved', 'archived')"
)
_OLD = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'awaiting_eob_confirmation', 'audit_running', "
    "'audit_complete', 'resolved', 'archived')"
)


def upgrade() -> None:
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _NEW)


def downgrade() -> None:
    op.execute(
        "UPDATE case_files SET status = 'audit_running' WHERE status = 'audit_incomplete'"
    )
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _OLD)
