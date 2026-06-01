"""Phase CO-3A — transparency_rates (+ staging) for cost-estimation price data.

Fresh tables, no backfill (DL-66). Staging mirrors live; new sources land in
staging first (DL-59) and promote to live after a ≥90% extraction-confidence
sample.

Revision ID: 0011
Revises:     0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_SOURCE_CHECK = "source IN ('medicare_pfs', 'hospital_mrf', 'tic_mrf', 'trilliant')"


def _columns() -> list:
    return [
        sa.Column(
            "rate_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_type", sa.Text(), nullable=True),
        sa.Column("payer", sa.Text(), nullable=True),
        sa.Column("hospital_id", sa.Text(), nullable=True),
        sa.Column("location_zip3", sa.Text(), nullable=True),
        sa.Column("rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("rate_type", sa.Text(), nullable=False),
        sa.Column("effective_year", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=False),
        sa.Column(
            "ingestion_timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("raw_metadata", postgresql.JSONB(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "transparency_rates",
        *_columns(),
        sa.PrimaryKeyConstraint("rate_id"),
        sa.CheckConstraint(_SOURCE_CHECK, name="ck_transparency_rates_source"),
    )
    op.create_index("idx_transparency_rates_code", "transparency_rates", ["code"])
    op.create_index(
        "idx_transparency_rates_code_location", "transparency_rates", ["code", "location_zip3"]
    )
    op.create_index(
        "idx_transparency_rates_payer",
        "transparency_rates",
        ["payer"],
        postgresql_where=sa.text("payer IS NOT NULL"),
    )
    op.create_index("idx_transparency_rates_source", "transparency_rates", ["source"])

    op.create_table(
        "transparency_rates_staging",
        *_columns(),
        sa.PrimaryKeyConstraint("rate_id"),
        sa.CheckConstraint(_SOURCE_CHECK, name="ck_transparency_rates_staging_source"),
    )
    op.create_index("idx_transparency_rates_staging_code", "transparency_rates_staging", ["code"])


def downgrade() -> None:
    op.drop_table("transparency_rates_staging")
    op.drop_index("idx_transparency_rates_source", table_name="transparency_rates")
    op.drop_index("idx_transparency_rates_payer", table_name="transparency_rates")
    op.drop_index("idx_transparency_rates_code_location", table_name="transparency_rates")
    op.drop_index("idx_transparency_rates_code", table_name="transparency_rates")
    op.drop_table("transparency_rates")
