"""Phase CO-9 Module 3 — admin verdict v2 (5 options + missed/hallucinated lists).

The CO-6A verdict CHECK allowed only correct/partially_correct/wrong. Module 3 adds
missed_finding / hallucinated / partial / unable_to_verify. The new CHECK is a SUPERSET
(keeps the legacy three so existing rows stay valid — no data migration). Adds
missed_findings + hallucinated_claims JSONB columns.

NOTE: this migration was not in the CO-9 prompt's 0012-0014 list, but extending the verdict
vocabulary requires a constraint change — added here as a necessary follow-on.

Revision ID: 0015
Revises:     0014
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_NEW = (
    "verdict IN ('correct', 'partially_correct', 'wrong', 'missed_finding', "
    "'hallucinated', 'partial', 'unable_to_verify')"
)
_OLD = "verdict IN ('correct', 'partially_correct', 'wrong')"


def upgrade() -> None:
    op.drop_constraint("ck_admin_verdicts_verdict", "admin_verdicts", type_="check")
    op.create_check_constraint("ck_admin_verdicts_verdict", "admin_verdicts", _NEW)
    op.add_column("admin_verdicts", sa.Column("missed_findings", postgresql.JSONB(), nullable=True))
    op.add_column(
        "admin_verdicts", sa.Column("hallucinated_claims", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("admin_verdicts", "hallucinated_claims")
    op.drop_column("admin_verdicts", "missed_findings")
    op.drop_constraint("ck_admin_verdicts_verdict", "admin_verdicts", type_="check")
    op.create_check_constraint("ck_admin_verdicts_verdict", "admin_verdicts", _OLD)
