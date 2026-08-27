"""Billing routes + the audit-gate dependency (Item 4, DL-16 — dark scaffold).

INERT while settings.enable_billing is False:
  * /billing/checkout and /billing/webhook return 404 (the feature doesn't exist yet),
  * /billing/status returns {"enabled": false} so the settings UI hides the section,
  * require_active_subscription_or_free_slot is a pure no-op (audits run unrestricted).

Stripe is walled off from PHI (DL-49): the only identifier we send Stripe is the user UUID.
Phone verification is intentionally NOT here (Twilio undecided — seam only).
"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.billing.accounts import (
    apply_subscription_state,
    free_analyses_remaining,
    get_or_create_account,
    subscription_active,
)
from app.billing.stripe_gateway import (
    BillingConfigError,
    create_checkout_session,
    event_to_state,
    verify_webhook_signature,
)
from app.config import get_settings
from app.db.session import get_session

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


def _require_enabled() -> None:
    """404 when billing is off — the endpoint must not appear to exist in the dark state."""
    if not get_settings().enable_billing:
        raise HTTPException(status_code=404, detail="Not Found")


async def require_active_subscription_or_free_slot(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Gate audit creation on an active subscription OR the one free analysis (DL-16). A pure
    no-op while enable_billing is False — the dark scaffold never restricts an audit."""
    settings = get_settings()
    if not settings.enable_billing:
        return
    acct = await get_or_create_account(session, user.user_id)
    if subscription_active(acct):
        return
    if free_analyses_remaining(acct) > 0:
        acct.free_analyses_used = (acct.free_analyses_used or 0) + 1
        await session.commit()
        return
    raise HTTPException(
        status_code=402,
        detail="You've used your free analysis. Subscribe to run more bill checks.",
    )


class CheckoutRequest(BaseModel):
    plan: str  # 'monthly' | 'yearly'


@router.post("/billing/checkout")
async def checkout(
    body: CheckoutRequest,
    user: CurrentUser = Depends(current_user),
):
    _require_enabled()
    if body.plan not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="plan must be 'monthly' or 'yearly'")
    try:
        url = await create_checkout_session(str(user.user_id), body.plan)
    except BillingConfigError as exc:
        log.error("billing.checkout.config_error", error=str(exc))
        raise HTTPException(status_code=503, detail="Billing is temporarily unavailable.") from exc
    return {"checkout_url": url}


@router.post("/billing/webhook")
async def webhook(request: Request, session: AsyncSession = Depends(get_session)):
    # Stripe calls this server-to-server — authenticated by the SIGNATURE, never a user session.
    _require_enabled()
    payload = await request.body()
    if not verify_webhook_signature(payload, request.headers.get("Stripe-Signature")):
        raise HTTPException(status_code=400, detail="invalid signature")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid payload") from exc
    # Idempotency (audit 2026-08-27 item 6): Stripe redelivers on any slow response —
    # insert-or-skip on the event id makes a redelivery a logged no-op, never a
    # re-applied state change. Events without an id (never real Stripe) process as before.
    event_id = event.get("id")
    if event_id:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.db.models.processed_stripe_events import ProcessedStripeEvent

        claimed = await session.execute(
            pg_insert(ProcessedStripeEvent)
            .values(event_id=str(event_id))
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        if claimed.rowcount == 0:
            log.info("billing.webhook.duplicate_skipped", event_id=event_id)
            return {"received": True}
    state = event_to_state(event)
    if state:
        await apply_subscription_state(session, **state)
    await session.commit()  # the idempotency claim persists even for ignored event types
    if state:
        log.info("billing.webhook.applied", event_type=event.get("type"))
    return {"received": True}


@router.get("/billing/status")
async def status(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    if not settings.enable_billing:
        return {"enabled": False}  # UI hides the billing section entirely
    acct = await get_or_create_account(session, user.user_id)
    await session.commit()
    return {
        "enabled": True,
        "active": subscription_active(acct),
        "status": acct.status,
        "plan": acct.plan,
        "current_period_end": (
            acct.current_period_end.isoformat() if acct.current_period_end else None
        ),
        "free_analyses_remaining": free_analyses_remaining(acct),
    }
