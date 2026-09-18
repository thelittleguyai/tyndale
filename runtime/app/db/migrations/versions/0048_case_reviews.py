"""case_reviews + admin_settings — Human Review Phase 1 queue (doc 39 §7, 2026-09-18).

One review row per case run; admin_settings is the durable store for the admin-settable
review_sample_pct dial. Chains onto 0047.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_reviews",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_file_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("case_files.case_file_id"), nullable=False),
        sa.Column("run_seq", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'unreviewed'")),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"),
                  nullable=True),
        sa.Column("verdict_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("admin_verdicts.verdict_id"), nullable=True),
        sa.Column("prior_review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("case_reviews.review_id"), nullable=True),
        sa.Column("terminal_status", sa.Text(), nullable=False),
        sa.Column("incomplete_reason", sa.Text(), nullable=True),
        sa.Column("confidence_band", sa.Text(), nullable=False,
                  server_default=sa.text("'unknown'")),
        sa.Column("triggers", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("sampled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("first_case", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("system_error", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("canary_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("material_disagreement", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("findings_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("documents_fingerprint", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("net_finding_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("in_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('unreviewed', 'in_review', 'approved', 'disapproved', 'cant_verify', "
            "'re_review')",
            name="ck_case_reviews_state",
        ),
        sa.CheckConstraint(
            "confidence_band IN ('high', 'medium', 'low', 'unknown')",
            name="ck_case_reviews_confidence_band",
        ),
    )
    op.create_index("idx_case_reviews_case_file", "case_reviews", ["case_file_id"])
    op.create_index("idx_case_reviews_state_enqueued", "case_reviews", ["state", "enqueued_at"])
    op.create_index("idx_case_reviews_decided_at", "case_reviews", ["decided_at"])
    op.create_table(
        "admin_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"),
                  nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("admin_settings")
    op.drop_index("idx_case_reviews_decided_at", table_name="case_reviews")
    op.drop_index("idx_case_reviews_state_enqueued", table_name="case_reviews")
    op.drop_index("idx_case_reviews_case_file", table_name="case_reviews")
    op.drop_table("case_reviews")
