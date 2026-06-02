"""conversations + messages (Phase CO-10 chat surface)

Two new tables backing the conversational chat surface:

  - conversations: one per chat thread. case_id NULL = freeform mode; case_id
    NOT NULL = per-case mode (FK -> case_files.case_file_id). Denormalised
    message_count + last_message_at keep the list view cheap.
  - messages: one per turn. content_chunks/tool_calls/citations are JSONB so the
    tiered (A/B/C) rendering, tool-call indicators, and citation chips all
    persist. status drives the streaming/stopped/failed UI.

DL-66 backfill note: both tables are brand-new, so the NOT NULL columns
(is_archived, message_count, role, status, ...) have no existing rows to
backfill — the server_default IS the value for any row inserted henceforth.

Revision chains onto 0015 (admin_verdict_v2 — the CO-9 head). NOTE: the source
prompt called this "0015"; 0015 was already taken, so this is 0016.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "message_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("conversation_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["case_id"], ["case_files.case_file_id"]),
    )
    op.create_index(
        "idx_conversations_user_id_updated_at",
        "conversations",
        ["user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "idx_conversations_case_id",
        "conversations",
        ["case_id"],
        postgresql_where=sa.text("case_id IS NOT NULL"),
    )
    op.create_index(
        "idx_conversations_freeform",
        "conversations",
        ["user_id", sa.text("updated_at DESC")],
        postgresql_where=sa.text("case_id IS NULL AND is_archived = FALSE"),
    )

    op.create_table(
        "messages",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_chunks", postgresql.JSONB(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_overall", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "status", sa.Text(), server_default=sa.text("'complete'"), nullable=False
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_usage_input", sa.Integer(), nullable=True),
        sa.Column("token_usage_output", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("message_id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.conversation_id"]
        ),
        sa.UniqueConstraint(
            "conversation_id", "sequence_number", name="uq_messages_conv_seq"
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')", name="ck_messages_role"
        ),
        sa.CheckConstraint(
            "status IN ('streaming', 'complete', 'stopped', 'failed')",
            name="ck_messages_status",
        ),
    )
    op.create_index(
        "idx_messages_conversation_id_sequence",
        "messages",
        ["conversation_id", "sequence_number"],
    )
    op.create_index(
        "idx_messages_streaming",
        "messages",
        ["conversation_id"],
        postgresql_where=sa.text("status = 'streaming'"),
    )


def downgrade() -> None:
    op.drop_index("idx_messages_streaming", table_name="messages")
    op.drop_index("idx_messages_conversation_id_sequence", table_name="messages")
    op.drop_table("messages")
    op.drop_index("idx_conversations_freeform", table_name="conversations")
    op.drop_index("idx_conversations_case_id", table_name="conversations")
    op.drop_index("idx_conversations_user_id_updated_at", table_name="conversations")
    op.drop_table("conversations")
