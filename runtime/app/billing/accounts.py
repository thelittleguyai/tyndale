"""Billing account DB helpers + the free-slot / subscription logic (Item 4, DL-16)."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.billing_accounts import BillingAccount

log = structlog.get_logger(__name__)

# Stripe subscription statuses that grant access.
_ACTIVE = {"active", "trialing"}


async def get_or_create_account(session: AsyncSession, user_id: uuid.UUID) -> BillingAccount:
    """The user's billing row, created (status 'none') on first touch."""
    acct = (
        await session.execute(
            select(BillingAccount).where(BillingAccount.user_id == user_id)
        )
    ).scalar_one_or_none()
    if acct is None:
        acct = BillingAccount(user_id=user_id, status="none")
        session.add(acct)
        await session.flush()
    return acct


def subscription_active(acct: BillingAccount) -> bool:
    return acct.status in _ACTIVE


def free_analyses_remaining(acct: BillingAccount) -> int:
    limit = get_settings().billing_free_analysis_limit
    return max(0, limit - (acct.free_analyses_used or 0))


async def apply_subscription_state(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    status: str,
    plan: str | None,
    current_period_end,
) -> None:
    """Idempotently write subscription state from a Stripe webhook. Locates the account by
    user_id (from checkout client_reference_id) or by stripe_customer_id (subscription events)."""
    acct: BillingAccount | None = None
    if user_id is not None:
        acct = (
            await session.execute(select(BillingAccount).where(BillingAccount.user_id == user_id))
        ).scalar_one_or_none()
        if acct is None:
            acct = BillingAccount(user_id=user_id, status="none")
            session.add(acct)
    elif stripe_customer_id is not None:
        acct = (
            await session.execute(
                select(BillingAccount).where(
                    BillingAccount.stripe_customer_id == stripe_customer_id
                )
            )
        ).scalar_one_or_none()
    if acct is None:
        log.warning("billing.webhook.no_matching_account", customer=bool(stripe_customer_id))
        return
    if stripe_customer_id:
        acct.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id:
        acct.stripe_subscription_id = stripe_subscription_id
    acct.status = status
    if plan is not None:
        acct.plan = plan
    if current_period_end is not None:
        acct.current_period_end = current_period_end
    await session.flush()
