"""Purge the e2e fixtures already sitting in the human-review queue (deep review C5).

Data-only. Before the queue learned to refuse synthetic identities (this release), every sweep
at dial 100 dropped ~22 `@e2e.tyndale.test` cases into case_reviews — the first thing a
reviewer would see. Removes the UNDECIDED rows for synthetic users; a row someone actually
reviewed (verdict_id set), or one a kept row links back to, stays. Idempotent; the downgrade
is a no-op (the rows were junk by the policy this release introduces). Chains onto 0051.
"""

from __future__ import annotations

from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM case_reviews r
        USING case_files cf, users u
        WHERE cf.case_file_id = r.case_file_id
          AND u.user_id = cf.user_id
          AND lower(u.email) LIKE '%@e2e.tyndale.test'
          AND r.verdict_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM case_reviews keep
              WHERE keep.prior_review_id = r.review_id AND keep.verdict_id IS NOT NULL
          )
        """
    )


def downgrade() -> None:
    pass
