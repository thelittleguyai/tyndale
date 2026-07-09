"""add 'not_a_bill' case status + member soft-delete columns

Upload-validation hardening (2026-07-09): a case must never dead-end on a 0-item encounter
screen. When the uploaded document(s) read fine but none is a bill/EOB, the audit degrades to the
distinct honest state 'not_a_bill' (nothing to audit) — separate from 'extraction_failed'
(couldn't read the docs). Add the value to the status CHECK so _set_status('not_a_bill') persists.

Also add member-initiated soft-delete: soft_deleted_at + soft_deleted_by, so a user can remove a
junk / mistaken case (no findings) without a hard delete. Every user-scoped list query filters
soft_deleted_at IS NULL.

Chains onto 0028.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

_NEW = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', 'encounter_verified', "
    "'awaiting_eob_confirmation', 'audit_running', 'audit_complete', 'audit_incomplete', "
    "'extraction_failed', 'not_a_bill', 'resolved', 'archived')"
)
_OLD = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', 'encounter_verified', "
    "'awaiting_eob_confirmation', 'audit_running', 'audit_complete', 'audit_incomplete', "
    "'extraction_failed', 'resolved', 'archived')"
)


def upgrade() -> None:
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _NEW)
    op.add_column(
        "case_files",
        sa.Column("soft_deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "case_files",
        sa.Column("soft_deleted_by", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_files", "soft_deleted_by")
    op.drop_column("case_files", "soft_deleted_at")
    # Collapse any not_a_bill cases to 'open' (a re-upload re-runs extraction) so the tighter
    # constraint re-applies without violation.
    op.execute("UPDATE case_files SET status = 'open' WHERE status = 'not_a_bill'")
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _OLD)
