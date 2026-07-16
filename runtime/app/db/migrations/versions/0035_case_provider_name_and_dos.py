"""add case_files.provider_name + date_of_service (typed)

Record row anatomy follow-up (2026-07-15). The provider name was only in unstructured finding /
line-item prose; the Record row now reads a TYPED field extracted at parse time (DL-39). Date of
service (not upload date) gets the same typed treatment.

Chains onto 0034.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_files", sa.Column("provider_name", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("date_of_service", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("case_files", "date_of_service")
    op.drop_column("case_files", "provider_name")
