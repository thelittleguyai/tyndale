"""BillingAccount model (Item 4, DL-16) — per-user subscription state + free-analysis ledger.

Dark scaffold: rows are only ever written when settings.enable_billing is True. Stripe is walled
off from PHI (DL-49) — this stores only Stripe's opaque customer/subscription IDs plus the plan +
period end, never a bill detail, diagnosis, or any health information. One row per user.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BillingAccount(Base):
    __tablename__ = "billing_accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('none', 'active', 'trialing', 'past_due', 'canceled', 'incomplete')",
            name="ck_billing_accounts_status",
        ),
        CheckConstraint(
            "plan IS NULL OR plan IN ('monthly', 'yearly')",
            name="ck_billing_accounts_plan",
        ),
    )

    billing_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, unique=True
    )
    # Opaque Stripe identifiers only (never PHI/PII from us — DL-49).
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'none' = no subscription; 'active'/'trialing' grant access. Mirrors Stripe's subscription
    # status vocabulary (the webhook writes it).
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'none'"))
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)  # monthly | yearly | NULL
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # DL-16: the free tier is one bill analysis; this is the ledger that enforces it.
    free_analyses_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
