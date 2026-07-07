"""billing_accounts — per-user subscription + free-analysis ledger (Item 4, DL-16 dark scaffold)

Inert until settings.enable_billing flips True. Chains onto 0026.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_accounts",
        sa.Column(
            "billing_account_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'none'")),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "free_analyses_used", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('none', 'active', 'trialing', 'past_due', 'canceled', 'incomplete')",
            name="ck_billing_accounts_status",
        ),
        sa.CheckConstraint(
            "plan IS NULL OR plan IN ('monthly', 'yearly')",
            name="ck_billing_accounts_plan",
        ),
    )


def downgrade() -> None:
    op.drop_table("billing_accounts")
