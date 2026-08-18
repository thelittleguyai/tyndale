"""secondary insurance — insurance_info.role + widened card types

Settings item 4 (2026-08-19): intake captured has_secondary_coverage into the case's
coverage blob, invisible afterward. Promotion: insurance_info gains role
('primary' default | 'secondary'), one row per (user, role); insurance_cards accepts
secondary_front/secondary_back so the same capture path serves the secondary card.
B6 groundwork only — capture-and-display; COB ordering/dollar logic stays untouched
(Brock's pending content).

Chains onto 0043.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "insurance_info",
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'primary'")),
    )
    op.create_check_constraint(
        "ck_insurance_info_role", "insurance_info", "role IN ('primary', 'secondary')"
    )
    op.drop_constraint("uq_insurance_info_user", "insurance_info", type_="unique")
    op.create_unique_constraint(
        "uq_insurance_info_user_role", "insurance_info", ["user_id", "role"]
    )
    op.drop_constraint("ck_insurance_cards_card_type", "insurance_cards", type_="check")
    op.create_check_constraint(
        "ck_insurance_cards_card_type",
        "insurance_cards",
        "card_type IN ('front', 'back', 'secondary_front', 'secondary_back')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM insurance_cards WHERE card_type LIKE 'secondary_%'")
    op.drop_constraint("ck_insurance_cards_card_type", "insurance_cards", type_="check")
    op.create_check_constraint(
        "ck_insurance_cards_card_type", "insurance_cards", "card_type IN ('front', 'back')"
    )
    op.execute("DELETE FROM insurance_info WHERE role = 'secondary'")
    op.drop_constraint("uq_insurance_info_user_role", "insurance_info", type_="unique")
    op.create_unique_constraint("uq_insurance_info_user", "insurance_info", ["user_id"])
    op.drop_constraint("ck_insurance_info_role", "insurance_info", type_="check")
    op.drop_column("insurance_info", "role")
