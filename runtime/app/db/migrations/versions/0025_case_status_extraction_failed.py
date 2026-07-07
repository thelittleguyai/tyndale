"""add 'extraction_failed' to the case_files status enum

When real OCR/translate produces no line items, the audit degrades VISIBLY to
'extraction_failed' rather than fabricating fixture line items (2026-07-06). Add the value to
the status CHECK so _set_status('extraction_failed') can persist it.

Chains onto 0024.
"""

from __future__ import annotations

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

_NEW = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', 'encounter_verified', "
    "'awaiting_eob_confirmation', 'audit_running', 'audit_complete', 'audit_incomplete', "
    "'extraction_failed', 'resolved', 'archived')"
)
_OLD = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', 'encounter_verified', "
    "'awaiting_eob_confirmation', 'audit_running', 'audit_complete', 'audit_incomplete', "
    "'resolved', 'archived')"
)


def upgrade() -> None:
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _NEW)


def downgrade() -> None:
    # Any degraded cases collapse back to 'open' (a re-upload re-runs extraction) so the tighter
    # constraint can be re-applied without violation.
    op.execute("UPDATE case_files SET status = 'open' WHERE status = 'extraction_failed'")
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _OLD)
