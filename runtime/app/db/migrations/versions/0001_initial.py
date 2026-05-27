"""initial schema — users, case_files, findings, deadlines, audit_events, feedback

Matches docs/integration-contracts.md Sections 2.2-2.4. Idempotent pgcrypto extension.

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_DEFAULT = sa.text("gen_random_uuid()")
NOW = sa.text("now()")
EMPTY_ARRAY = sa.text("'[]'::jsonb")
EMPTY_OBJ = sa.text("'{}'::jsonb")


def upgrade() -> None:
    # gen_random_uuid() lives in pgcrypto. Idempotent so re-runs are safe.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("service_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("improvement_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "case_files",
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.Column("documents", postgresql.JSONB(), server_default=EMPTY_ARRAY, nullable=False),
        sa.Column("coverage", postgresql.JSONB(), nullable=True),
        sa.Column("eobs", postgresql.JSONB(), server_default=EMPTY_ARRAY, nullable=False),
        sa.Column("plan_current", postgresql.JSONB(), nullable=True),
        sa.Column("plan_history", postgresql.JSONB(), server_default=EMPTY_ARRAY, nullable=False),
        sa.Column("research_log", postgresql.JSONB(), server_default=EMPTY_ARRAY, nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("case_file_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_case_files_user"),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'archived')",
            name="ck_case_files_status",
        ),
    )

    op.create_table(
        "findings",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("subagent_source", sa.Text(), nullable=False),
        sa.Column("voice_tier", sa.Text(), nullable=False),
        sa.Column("facts", postgresql.JSONB(), nullable=False),
        sa.Column("legal_claim", postgresql.JSONB(), nullable=True),
        sa.Column("recommendation", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("finding_id"),
        sa.ForeignKeyConstraint(["case_file_id"], ["case_files.case_file_id"], name="fk_findings_case_file"),
        sa.CheckConstraint("voice_tier IN ('A', 'B', 'C')", name="ck_findings_voice_tier"),
    )
    op.create_index("idx_findings_case_file", "findings", ["case_file_id"])

    op.create_table(
        "deadlines",
        sa.Column("deadline_id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deadline_date", sa.Date(), nullable=False),
        sa.Column("deadline_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("notified_thresholds", postgresql.JSONB(), server_default=EMPTY_ARRAY, nullable=False),
        sa.PrimaryKeyConstraint("deadline_id"),
        sa.ForeignKeyConstraint(["case_file_id"], ["case_files.case_file_id"], name="fk_deadlines_case_file"),
        sa.CheckConstraint("status IN ('pending', 'completed', 'missed')", name="ck_deadlines_status"),
    )
    op.create_index("idx_deadlines_case_file_date", "deadlines", ["case_file_id", "deadline_date"])

    op.create_table(
        "audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("payload_hash", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("skill_version", sa.Text(), nullable=True),
        sa.Column("prompt_template_version", sa.Text(), nullable=True),
        sa.Column("retrieved_chunks", postgresql.JSONB(), nullable=True),
        sa.Column("tools_invoked", postgresql.JSONB(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
        sa.CheckConstraint(
            "event_type IN ('tool_invocation', 'subagent_call', 'model_call', "
            "'user_action', 'system_action', 'hook_invocation')",
            name="ck_audit_events_event_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'error', 'timeout', 'blocked')",
            name="ck_audit_events_outcome",
        ),
    )
    op.create_index("idx_audit_events_case_file", "audit_events", ["case_file_id"])
    op.create_index("idx_audit_events_user", "audit_events", ["user_id"])
    op.create_index("idx_audit_events_timestamp", "audit_events", ["timestamp"])

    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("response_id", sa.Text(), nullable=True),
        sa.Column("feedback_type", sa.Text(), nullable=False),
        sa.Column("improvement_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "feedback_triage_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("feedback_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("enqueued_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"], name="fk_triage_feedback_event"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'done', 'failed')",
            name="ck_feedback_triage_status",
        ),
    )

    op.create_table(
        "feedback_deid_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("feedback_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deid_payload", postgresql.JSONB(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("deid_metadata", postgresql.JSONB(), server_default=EMPTY_OBJ, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"], name="fk_deid_feedback_event"),
    )


def downgrade() -> None:
    op.drop_table("feedback_deid_candidates")
    op.drop_table("feedback_triage_queue")
    op.drop_table("feedback_events")
    op.drop_index("idx_audit_events_timestamp", table_name="audit_events")
    op.drop_index("idx_audit_events_user", table_name="audit_events")
    op.drop_index("idx_audit_events_case_file", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("idx_deadlines_case_file_date", table_name="deadlines")
    op.drop_table("deadlines")
    op.drop_index("idx_findings_case_file", table_name="findings")
    op.drop_table("findings")
    op.drop_table("case_files")
    op.drop_table("users")
