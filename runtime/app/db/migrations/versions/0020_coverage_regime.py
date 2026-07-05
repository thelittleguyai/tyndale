"""coverage_regime + regime_detection on case_files and insurance_info

Sprint B (DL-82): the seven coverage regimes. Adds a CHECK-constrained
``coverage_regime`` string + a ``regime_detection`` JSONB (method/confidence/
evidence/verified) to both the case-file coverage surface and the user's
insurance_info row. Backfills ``commercial`` ONLY where an existing record is
CLEARLY commercial (a group number + payer, no government-coverage moniker);
everything else stays NULL so the intake ladder asks rather than guessing.

Chains onto 0019.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_REGIMES = (
    "'commercial', 'medicare_traditional', 'medicare_advantage', 'medicaid', "
    "'dual_qmb', 'self_pay', 'tricare_va'"
)

# "Clearly commercial" backfill = a group number + a payer/insurer present, and no
# government-coverage word anywhere in the record. Conservative on purpose — a false
# 'commercial' backfill would route a Medicare case down the wrong path (below).


def upgrade() -> None:
    # --- case_files ---
    op.add_column("case_files", sa.Column("coverage_regime", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("regime_detection", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_case_files_coverage_regime",
        "case_files",
        f"coverage_regime IS NULL OR coverage_regime IN ({_REGIMES})",
    )
    op.execute(
        """
        UPDATE case_files
           SET coverage_regime = 'commercial',
               regime_detection = jsonb_build_object(
                   'regime', 'commercial',
                   'candidate', 'commercial',
                   'confidence', 'low',
                   'method', 'backfill',
                   'evidence', jsonb_build_array('0020 backfill: group number + payer, no government-coverage moniker'),
                   'verified', false
               )
         WHERE coverage_regime IS NULL
           AND coverage ->> 'group_number' IS NOT NULL
           AND COALESCE(coverage ->> 'payer_name', coverage ->> 'insurer') IS NOT NULL
           AND lower(coverage::text) NOT LIKE '%medicare%'
           AND lower(coverage::text) NOT LIKE '%medicaid%'
           AND lower(coverage::text) NOT LIKE '%tricare%'
           AND lower(coverage::text) NOT LIKE '%champva%'
           AND lower(coverage::text) NOT LIKE '%veterans%'
        """
    )

    # --- insurance_info ---
    op.add_column("insurance_info", sa.Column("coverage_regime", sa.Text(), nullable=True))
    op.add_column("insurance_info", sa.Column("regime_detection", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_insurance_info_coverage_regime",
        "insurance_info",
        f"coverage_regime IS NULL OR coverage_regime IN ({_REGIMES})",
    )
    op.execute(
        """
        UPDATE insurance_info
           SET coverage_regime = 'commercial',
               regime_detection = jsonb_build_object(
                   'regime', 'commercial',
                   'candidate', 'commercial',
                   'confidence', 'low',
                   'method', 'backfill',
                   'evidence', jsonb_build_array('0020 backfill: group number + insurer, no government-coverage moniker'),
                   'verified', false
               )
         WHERE coverage_regime IS NULL
           AND group_number IS NOT NULL
           AND insurer IS NOT NULL
           AND medicare_medicaid_id IS NULL
           AND medicare_part_a_date IS NULL
           AND medicare_part_b_date IS NULL
           AND lower(insurer) NOT LIKE '%medicare%'
           AND lower(insurer) NOT LIKE '%medicaid%'
           AND lower(insurer) NOT LIKE '%tricare%'
           AND lower(COALESCE(plan_name, '')) NOT LIKE '%medicare%'
           AND lower(COALESCE(plan_name, '')) NOT LIKE '%medicaid%'
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_insurance_info_coverage_regime", "insurance_info", type_="check")
    op.drop_column("insurance_info", "regime_detection")
    op.drop_column("insurance_info", "coverage_regime")

    op.drop_constraint("ck_case_files_coverage_regime", "case_files", type_="check")
    op.drop_column("case_files", "regime_detection")
    op.drop_column("case_files", "coverage_regime")
