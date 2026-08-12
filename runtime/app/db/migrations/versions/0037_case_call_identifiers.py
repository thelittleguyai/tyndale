"""add case_files claim_number / account_number / provider_phone / payer_phone (typed)

Delta B4 / conformance H6-L7 (2026-08-12). The call scripts and the call-mode pinned strip
need the identifiers the user reads aloud and the number they dial. Same treatment as
provider_name in 0035: extracted TYPED at parse time (DL-39), never regexed out of prose.

All four are nullable — a document that doesn't print one leaves it NULL, and the renderer
degrades rather than guessing.

Chains onto 0036.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_files", sa.Column("claim_number", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("account_number", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("provider_phone", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("payer_phone", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("case_files", "payer_phone")
    op.drop_column("case_files", "provider_phone")
    op.drop_column("case_files", "account_number")
    op.drop_column("case_files", "claim_number")
