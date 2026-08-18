"""plan_documents — the plan-level SBC home

Settings item 5 (2026-08-19): an SBC describes the PLAN, not one bill, so it gets a
user-level home. One upload satisfies the SBC checklist line on every case and feeds
rung-2 coverage terms when a case has none of its own. Bytes live in Blob (blob_ref);
`coverage` holds the high-confidence SBC term extraction.

Chains onto 0044.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_documents",
        sa.Column(
            "plan_document_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False
        ),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("blob_ref", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("coverage", JSONB(), nullable=True),
        sa.Column("ocr_text_chars", sa.Integer(), nullable=True),
        sa.Column("extraction_status", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_plan_documents_user_id", "plan_documents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_documents_user_id", table_name="plan_documents")
    op.drop_table("plan_documents")
