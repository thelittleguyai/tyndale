"""Human Review — split `canary` (a planted marker leaked) from `guard_drop` (a fabrication
guard removed or downgraded something) — e2e 2026-09-23 M6 / B2.

The queue row's `canary_flag` fired on ANY tripwire, so the specimen case read `canary: true`
with zero fixture markers in sight — Brock's "canary events" filter and the always-enqueue
trigger had come to mean "the guard did something". Two columns now:

  * ``canary_flag``      — a tripwire whose codes include a planted marker (02417 / 05821 / Z4411)
  * ``guard_drop_flag``  — a tripwire that dropped / regenerated / degraded / downgraded

Backfill from the case's own tripwire log: every existing flag becomes a guard_drop flag, and
canary is recomputed from the marker set. Chains onto 0055.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

_MARKERS = "array['02417','05821','Z4411']"


def upgrade() -> None:
    op.add_column(
        "case_reviews",
        sa.Column("guard_drop_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # what canary_flag meant until now: "a guard fired"
    op.execute("UPDATE case_reviews SET guard_drop_flag = canary_flag")
    # what canary means from now on: a planted marker in a tripwire's codes
    op.execute(
        f"""
        UPDATE case_reviews r SET canary_flag = EXISTS (
            SELECT 1 FROM case_files cf,
                 jsonb_array_elements(coalesce(cf.research_log, '[]'::jsonb)) e
            WHERE cf.case_file_id = r.case_file_id
              AND e->>'kind' = 'tripwire'
              AND (e->'codes') ?| {_MARKERS}
        )
        """
    )
    op.execute("UPDATE case_reviews SET triggers = (triggers - 'canary') || '[\"guard_drop\"]'::jsonb WHERE triggers ? 'canary' AND guard_drop_flag AND NOT canary_flag")


def downgrade() -> None:
    op.execute("UPDATE case_reviews SET canary_flag = canary_flag OR guard_drop_flag")
    op.execute("UPDATE case_reviews SET triggers = (triggers - 'guard_drop') || '[\"canary\"]'::jsonb WHERE triggers ? 'guard_drop' AND NOT (triggers ? 'canary')")
    op.drop_column("case_reviews", "guard_drop_flag")
