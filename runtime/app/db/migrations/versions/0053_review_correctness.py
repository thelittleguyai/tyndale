"""Human Review correctness (deep review, 2026-09-18).

  * uq_case_reviews_case_run (case_file_id, run_seq) — two concurrent terminal transitions
    could both insert the same run. Existing duplicates are renumbered first (dense per case,
    oldest first) so the constraint can be created on a live table.
  * case_files.audit_summary — the Lead Planner summary was never persisted: every read after
    the finalize response (the user's re-fetch, the thread projection, the reviewer's Analysis
    tab) assembled with an empty string. The reviewer must see what the user read.
  * analytics_events.actor_user_id — who ACTED, when that is not the subject (an admin's
    verdict on a patient's case). user_id stays the subject.

Chains onto 0052.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE case_reviews r SET run_seq = d.rn
        FROM (
            SELECT review_id,
                   row_number() OVER (PARTITION BY case_file_id ORDER BY run_seq, enqueued_at, review_id) AS rn
            FROM case_reviews
        ) d
        WHERE d.review_id = r.review_id AND r.run_seq <> d.rn
        """
    )
    op.create_unique_constraint("uq_case_reviews_case_run", "case_reviews", ["case_file_id", "run_seq"])
    op.add_column("case_files", sa.Column("audit_summary", sa.Text(), nullable=True))
    op.add_column(
        "analytics_events",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analytics_events", "actor_user_id")
    op.drop_column("case_files", "audit_summary")
    op.drop_constraint("uq_case_reviews_case_run", "case_reviews", type_="unique")
