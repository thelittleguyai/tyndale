"""plan_types v2 — reconcile coverage_regime to the 14-value enum + coverage_attributes

Brock memo 2026-07-06 (approved). The shipped 7-value coverage_regime CHECK (0020) is replaced by
the canonical 14. Stored values are migrated: commercial→state_regulated_commercial,
medicaid→medicaid_ffs, tricare_va→tricare, dual_qmb→dual_eligible. Adds a coverage_attributes
JSONB (typed attributes validated in code — app.plan_types). Chains onto 0027.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

# The 14 canonical regimes (snapshot — migrations don't import evolving app constants).
_V2 = (
    "state_regulated_commercial", "erisa_self_funded", "medicare_traditional",
    "medicare_advantage", "medicaid_ffs", "medicaid_mco", "dual_eligible", "self_pay",
    "tricare", "va_champva", "fehb_pshb", "nonfederal_governmental", "stldi", "excepted_coverage",
)
_V1 = (
    "commercial", "medicare_traditional", "medicare_advantage", "medicaid",
    "dual_qmb", "self_pay", "tricare_va",
)
_IN_V2 = ", ".join(f"'{t}'" for t in _V2)
_IN_V1 = ", ".join(f"'{t}'" for t in _V1)

# up-migration value renames (old → new)
_UP = {
    "commercial": "state_regulated_commercial",
    "medicaid": "medicaid_ffs",
    "tricare_va": "tricare",
    "dual_qmb": "dual_eligible",
}
# down-migration collapses (new → old); new-only regimes have no v1 equivalent → NULL
_DOWN = {
    "state_regulated_commercial": "commercial",
    "medicaid_ffs": "medicaid",
    "medicaid_mco": "medicaid",
    "dual_eligible": "dual_qmb",
    "tricare": "tricare_va",
    "va_champva": "tricare_va",
}
_DOWN_TO_NULL = ("erisa_self_funded", "fehb_pshb", "nonfederal_governmental", "stldi", "excepted_coverage")
_TABLES = ("case_files", "insurance_info")


def upgrade() -> None:
    for tbl in _TABLES:
        ck = f"ck_{tbl}_coverage_regime"
        op.drop_constraint(ck, tbl, type_="check")
        for old, new in _UP.items():
            op.execute(f"UPDATE {tbl} SET coverage_regime = '{new}' WHERE coverage_regime = '{old}'")
        op.create_check_constraint(
            ck, tbl, f"coverage_regime IS NULL OR coverage_regime IN ({_IN_V2})"
        )
        op.add_column(tbl, sa.Column("coverage_attributes", JSONB(), nullable=True))


def downgrade() -> None:
    for tbl in _TABLES:
        ck = f"ck_{tbl}_coverage_regime"
        op.drop_column(tbl, "coverage_attributes")
        op.drop_constraint(ck, tbl, type_="check")
        for new, old in _DOWN.items():
            op.execute(f"UPDATE {tbl} SET coverage_regime = '{old}' WHERE coverage_regime = '{new}'")
        for gone in _DOWN_TO_NULL:
            op.execute(f"UPDATE {tbl} SET coverage_regime = NULL WHERE coverage_regime = '{gone}'")
        op.create_check_constraint(
            ck, tbl, f"coverage_regime IS NULL OR coverage_regime IN ({_IN_V1})"
        )
