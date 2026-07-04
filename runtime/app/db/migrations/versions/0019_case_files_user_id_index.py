"""index on case_files.user_id

Every dashboard / intake / user-scoped query filters case_files by ``user_id``
(app/routes/admin/cases.py list_cases, the dashboard payload, intake), yet the
column had no index — those lookups sequential-scanned. Add ``idx_case_files_user_id``.

Chains onto 0018.
"""

from __future__ import annotations

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_case_files_user_id",
        "case_files",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_case_files_user_id", table_name="case_files")
