"""add 'interrupted' to the cron_run_log status enum

The startup reconciliation sweep (2026-07-06) closes cron_run_log rows stuck in 'running'
whose owning process died (SIGKILL / deploy roll) as 'interrupted' — distinct from a logic
'failed'. Add it to the CHECK.

Chains onto 0023.
"""

from __future__ import annotations

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

_NEW = "status IN ('running', 'success', 'failed', 'partial', 'interrupted')"
_OLD = "status IN ('running', 'success', 'failed', 'partial')"


def upgrade() -> None:
    op.drop_constraint("ck_cron_run_log_status", "cron_run_log", type_="check")
    op.create_check_constraint("ck_cron_run_log_status", "cron_run_log", _NEW)


def downgrade() -> None:
    op.execute("UPDATE cron_run_log SET status = 'failed' WHERE status = 'interrupted'")
    op.drop_constraint("ck_cron_run_log_status", "cron_run_log", type_="check")
    op.create_check_constraint("ck_cron_run_log_status", "cron_run_log", _OLD)
