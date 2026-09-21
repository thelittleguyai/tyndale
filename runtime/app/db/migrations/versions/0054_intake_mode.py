"""Guided intake, Phase 1 (doc 40 §D) — which front door a user gets, and which one made a case.

  * users.intake_mode — an ADMIN OVERRIDE ('guided' | 'chat_first'); null = no override.
  * users.intake_cohort — the cohort decision, made ONCE at first sign-in so moving the
    cohort dial later never flips a user who is mid-journey: 'guided' (assigned) |
    'default' (decided: follows the env default). null = not decided yet.
  * case_files.intake_mode — the route that CREATED the case, so the Human Review queue and
    the analytics compare both front doors in one place. Every existing case came in through
    upload, so the backfill is 'chat_first' and the column is NOT NULL from here on.
  * analytics_events.intake_mode — stamped by the emitter on every case-scoped event.

Chains onto 0053.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

_MODES = "('guided', 'chat_first')"


def upgrade() -> None:
    op.add_column("users", sa.Column("intake_mode", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("intake_cohort", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_users_intake_mode", "users", f"intake_mode IS NULL OR intake_mode IN {_MODES}"
    )
    op.create_check_constraint(
        "ck_users_intake_cohort",
        "users",
        "intake_cohort IS NULL OR intake_cohort IN ('guided', 'default')",
    )
    op.add_column(
        "case_files",
        sa.Column("intake_mode", sa.Text(), nullable=False, server_default="chat_first"),
    )
    op.create_check_constraint(
        "ck_case_files_intake_mode", "case_files", f"intake_mode IN {_MODES}"
    )
    # Every case-scoped analytics event carries its case's front door, stamped by the emitter.
    # No backfill: rows before this migration predate the guided route and stay null.
    op.add_column("analytics_events", sa.Column("intake_mode", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_analytics_events_intake_mode",
        "analytics_events",
        f"intake_mode IS NULL OR intake_mode IN {_MODES}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analytics_events_intake_mode", "analytics_events", type_="check")
    op.drop_column("analytics_events", "intake_mode")
    op.drop_constraint("ck_case_files_intake_mode", "case_files", type_="check")
    op.drop_column("case_files", "intake_mode")
    op.drop_constraint("ck_users_intake_cohort", "users", type_="check")
    op.drop_constraint("ck_users_intake_mode", "users", type_="check")
    op.drop_column("users", "intake_cohort")
    op.drop_column("users", "intake_mode")
