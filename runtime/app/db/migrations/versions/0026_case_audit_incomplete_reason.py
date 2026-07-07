"""persist the audit-incomplete reason on case_files (needs_documents | system_error)

An audit_incomplete case must say WHY: 'needs_documents' (user-actionable — the audit ran and
found things, but the three-number computation is blocked on missing inputs) vs 'system_error'
(budget/citation/provider failure). The reason is set at finalize and read back by GET
/v1/audit/{id} so the app renders the honest terminal screen (2026-07-07).

Chains onto 0025.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_CK = "ck_case_files_audit_incomplete_reason"
_CK_SQL = (
    "audit_incomplete_reason IS NULL OR "
    "audit_incomplete_reason IN ('needs_documents', 'system_error')"
)


def upgrade() -> None:
    op.add_column("case_files", sa.Column("audit_incomplete_reason", sa.Text(), nullable=True))
    op.create_check_constraint(_CK, "case_files", _CK_SQL)


def downgrade() -> None:
    op.drop_constraint(_CK, "case_files", type_="check")
    op.drop_column("case_files", "audit_incomplete_reason")
