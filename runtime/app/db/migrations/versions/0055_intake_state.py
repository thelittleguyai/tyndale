"""Guided intake, Phase 1 (doc 40 §A4, §A8) — the planner's own bookkeeping for a case.

case_files.intake_state (JSONB, nullable) holds ONLY what no engine seam already owns:

  * ``skipped`` / ``acked`` — screens the user chose to pass ("I don't have it") or has seen
    (the welcome, the facts-only boundary, the bill read-back). Everything the user actually
    TELLS us still lands where it always did — coverage, attest_status, encounter_confirmations.
  * ``progress_high_water`` — the progress segments that have EVER been filled. §A8: the bar
    never regresses; if a document is reclassified the segment stays and a note explains.
  * ``answers`` — plain-language answers with no engine home yet (the coverage-type ask).
  * ``completeness_at_count`` — how many EOBs the user was shown when they confirmed "that's
    all of them", so adding one afterwards re-asks (locked 5d: asked EVERY time).

Chains onto 0054.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_files", sa.Column("intake_state", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("case_files", "intake_state")
