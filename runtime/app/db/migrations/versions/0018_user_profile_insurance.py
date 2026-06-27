"""user profile fields + insurance_info + insurance_cards (Phase CO-17, DL-78)

Adds onboarding/profile columns to ``users`` (name / DOB / profile_completed gate)
and two new tables: ``insurance_info`` (one IDENTIFIED row per user — the extracted
card data) and ``insurance_cards`` (one row per side; the IMAGE lives in Azure Blob
via blob_ref, never base64 in Postgres).

DL-66 backfill: ``profile_completed`` defaults FALSE. Existing users all have a null
first_name/date_of_birth (new columns), so they are all marked incomplete and prompted
through onboarding ONCE — a deliberate judgment call (re-collect the new required fields)
distinct from CO-1A's silent grandfathering. Chains onto 0017.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: profile/onboarding columns ----------------------------------
    op.add_column("users", sa.Column("first_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "profile_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("profile_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # --- insurance_info: one identified row per user ------------------------
    op.create_table(
        "insurance_info",
        sa.Column(
            "insurance_info_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("insurer", sa.Text(), nullable=True),
        sa.Column("plan_name", sa.Text(), nullable=True),
        sa.Column("plan_number", sa.Text(), nullable=True),
        sa.Column("plan_type", sa.Text(), nullable=True),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("member_id_prefix", sa.Text(), nullable=True),
        sa.Column("member_id_suffix", sa.Text(), nullable=True),
        sa.Column("group_number", sa.Text(), nullable=True),
        sa.Column("member_name", sa.Text(), nullable=True),
        sa.Column("member_birth_date", sa.Date(), nullable=True),
        sa.Column("member_gender", sa.Text(), nullable=True),
        sa.Column("member_employer", sa.Text(), nullable=True),
        sa.Column("payer_id", sa.Text(), nullable=True),
        sa.Column("payer_phone", sa.Text(), nullable=True),
        sa.Column("payer_address", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("rx_bin", sa.Text(), nullable=True),
        sa.Column("rx_pcn", sa.Text(), nullable=True),
        sa.Column("rx_grp", sa.Text(), nullable=True),
        sa.Column("rx_id", sa.Text(), nullable=True),
        sa.Column("rx_plan", sa.Text(), nullable=True),
        sa.Column("pbm", sa.Text(), nullable=True),
        sa.Column("medicare_medicaid_id", sa.Text(), nullable=True),
        sa.Column("medicare_part_a_date", sa.Date(), nullable=True),
        sa.Column("medicare_part_b_date", sa.Date(), nullable=True),
        sa.Column("copays", postgresql.JSONB(), nullable=True),
        sa.Column("dependents", postgresql.JSONB(), nullable=True),
        sa.Column("raw_extracted", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_status", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("insurance_info_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.UniqueConstraint("user_id", name="uq_insurance_info_user"),
    )

    # --- insurance_cards: one row per side; image bytes live in Blob --------
    op.create_table(
        "insurance_cards",
        sa.Column(
            "insurance_card_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_type", sa.Text(), nullable=False),
        sa.Column("blob_ref", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("raw_ocr_json", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_status", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("insurance_card_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.CheckConstraint("card_type IN ('front', 'back')", name="ck_insurance_cards_card_type"),
        sa.UniqueConstraint("user_id", "card_type", name="uq_insurance_cards_user_type"),
    )


def downgrade() -> None:
    op.drop_table("insurance_cards")
    op.drop_table("insurance_info")
    op.drop_column("users", "profile_completed_at")
    op.drop_column("users", "profile_completed")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
