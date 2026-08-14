"""partial unique index on (conversation_id, payload->>'marker')

Deep review finding 7. Bridge idempotency was check-then-insert with nothing underneath it, so
two concurrent writers could both read "not posted yet" and both insert — losing a reconcile
silently. The app-level check stays (it handles the ordinary case without an exception), but
the invariant now lives in the database, where a race can't step over it.

Partial: only rows whose payload actually carries a marker are constrained. Ordinary thread
messages have no marker and are free to repeat — a user can say the same thing twice.

Pre-existing duplicates would make this index fail to build. It de-duplicates first, keeping
the EARLIEST row per (conversation, marker): the thread is a chronological projection, so the
first time we said something is the true one.

Chains onto 0038.
"""

from __future__ import annotations

from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

_INDEX = "uq_messages_conversation_marker"


def upgrade() -> None:
    # Collapse any duplicates that predate the constraint, keeping the earliest.
    op.execute(
        """
        DELETE FROM messages m
        USING messages keep
        WHERE m.conversation_id = keep.conversation_id
          AND m.payload->>'marker' IS NOT NULL
          AND keep.payload->>'marker' IS NOT NULL
          AND m.payload->>'marker' = keep.payload->>'marker'
          AND (m.created_at, m.message_id) > (keep.created_at, keep.message_id)
        """
    )
    op.execute(
        f"CREATE UNIQUE INDEX {_INDEX} ON messages (conversation_id, (payload->>'marker')) "
        "WHERE payload->>'marker' IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
