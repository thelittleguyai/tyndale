"""add 'verification_suggestion' to the messages kind CHECK

Chat-first Phase B (D4b, DL-91). A free-text verification reply is mapped to the cards + intended
answer and rendered as a pre-selectable suggestion thread entry (never a confirmation — the tap
commits). Add the kind so thread_bridge can persist it.

Chains onto 0030.
"""

from __future__ import annotations

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

_NEW = (
    "kind IN ('message', 'status_card_update', 'system_message', 'moment_card', "
    "'verification_request', 'verification_suggestion')"
)
_OLD = (
    "kind IN ('message', 'status_card_update', 'system_message', 'moment_card', "
    "'verification_request')"
)


def upgrade() -> None:
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.create_check_constraint("ck_messages_kind", "messages", _NEW)


def downgrade() -> None:
    op.execute("UPDATE messages SET kind = 'system_message' WHERE kind = 'verification_suggestion'")
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.create_check_constraint("ck_messages_kind", "messages", _OLD)
