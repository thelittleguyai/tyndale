"""Phase CO-8 — allow 'phi_block' in audit_events.event_type.

The send_email PHI guardrail (DL-47) writes an audit row with
event_type='phi_block' on every blocked send. The original CHECK constraint
(migration 0001) didn't include it, so this migration widens the allowed set.
Idempotent: drops the named constraint if present, then re-adds it with the
extended list. down() restores the original set.

Revision ID: 0007
Revises:     0006
"""

from __future__ import annotations

from alembic import op

# Alembic identifiers
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_BASE_TYPES = (
    "'tool_invocation', 'subagent_call', 'model_call', "
    "'user_action', 'system_action', 'hook_invocation'"
)
_OLD = f"event_type IN ({_BASE_TYPES})"
_NEW = f"event_type IN ({_BASE_TYPES}, 'phi_block')"


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS ck_audit_events_event_type")
    op.execute(f"ALTER TABLE audit_events ADD CONSTRAINT ck_audit_events_event_type CHECK ({_NEW})")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS ck_audit_events_event_type")
    op.execute(f"ALTER TABLE audit_events ADD CONSTRAINT ck_audit_events_event_type CHECK ({_OLD})")
