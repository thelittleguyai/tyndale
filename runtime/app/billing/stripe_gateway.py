"""Stripe gateway (Item 4) — hosted Checkout + signature-verified webhook, zero SDK.

Kept dependency-free (httpx + hmac) so a DISABLED feature adds no image weight. Stripe is walled
off from PHI (DL-49): create_checkout_session sends only the user UUID (client_reference_id) + a
price id; Stripe's hosted page collects email/payment. We never send Stripe an email or any bill/
health detail.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_STRIPE_API = "https://api.stripe.com/v1"
_SIG_TOLERANCE_S = 300  # reject webhook signatures whose timestamp is >5 min skewed (replay guard)


class BillingConfigError(RuntimeError):
    """Billing is enabled but a required Stripe setting is missing."""


def _price_id(plan: str) -> str:
    s = get_settings()
    price = {"monthly": s.stripe_price_monthly, "yearly": s.stripe_price_yearly}.get(plan)
    if not price:
        raise BillingConfigError(f"no Stripe price configured for plan {plan!r}")
    return price


def plan_for_price(price_id: str | None) -> str | None:
    s = get_settings()
    if price_id and price_id == s.stripe_price_monthly:
        return "monthly"
    if price_id and price_id == s.stripe_price_yearly:
        return "yearly"
    return None


async def create_checkout_session(user_id: str, plan: str) -> str:
    """Create a Stripe hosted Checkout session for a subscription; return its URL. Sends ONLY the
    user UUID (client_reference_id) + the price — no email/PHI (DL-49)."""
    s = get_settings()
    if not s.stripe_secret_key:
        raise BillingConfigError("STRIPE_SECRET_KEY is not configured")
    data = {
        "mode": "subscription",
        "line_items[0][price]": _price_id(plan),
        "line_items[0][quantity]": "1",
        "client_reference_id": str(user_id),  # our UUID — the only identifier we send
        "success_url": s.billing_checkout_success_url,
        "cancel_url": s.billing_checkout_cancel_url,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_STRIPE_API}/checkout/sessions",
            data=data,
            headers={"Authorization": f"Bearer {s.stripe_secret_key}"},
        )
    if r.status_code >= 400:
        log.error("billing.checkout.stripe_error", status=r.status_code)
        raise BillingConfigError(f"Stripe checkout failed ({r.status_code})")
    return r.json()["url"]


def verify_webhook_signature(payload: bytes, sig_header: str | None, now: int | None = None) -> bool:
    """Verify Stripe's `Stripe-Signature` header (t=…,v1=… HMAC-SHA256 over "{t}.{payload}").
    Constant-time compare + a timestamp-skew replay guard. False on any malformed/failed check."""
    s = get_settings()
    secret = s.stripe_webhook_secret
    if not secret or not sig_header:
        return False
    parts = dict(
        p.split("=", 1) for p in sig_header.split(",") if "=" in p
    )
    ts, v1 = parts.get("t"), parts.get("v1")
    if not ts or not v1:
        return False
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    current = now if now is not None else int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    if abs(current - ts_int) > _SIG_TOLERANCE_S:
        return False
    signed = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def event_to_state(event: dict) -> dict | None:
    """Map a Stripe event to apply_subscription_state kwargs, or None to ignore the event."""
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    if etype == "checkout.session.completed":
        ref = obj.get("client_reference_id")
        return {
            "user_id": _as_uuid(ref),
            "stripe_customer_id": obj.get("customer"),
            "stripe_subscription_id": obj.get("subscription"),
            "status": "active",
            "plan": None,
            "current_period_end": None,
        }
    if etype in ("customer.subscription.updated", "customer.subscription.created"):
        price = (((obj.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get("id")
        return {
            "user_id": None,
            "stripe_customer_id": obj.get("customer"),
            "stripe_subscription_id": obj.get("id"),
            "status": obj.get("status", "active"),
            "plan": plan_for_price(price),
            "current_period_end": _as_dt(obj.get("current_period_end")),
        }
    if etype == "customer.subscription.deleted":
        return {
            "user_id": None,
            "stripe_customer_id": obj.get("customer"),
            "stripe_subscription_id": obj.get("id"),
            "status": "canceled",
            "plan": None,
            "current_period_end": _as_dt(obj.get("current_period_end")),
        }
    return None


def _as_uuid(v):
    import uuid

    try:
        return uuid.UUID(str(v)) if v else None
    except (ValueError, TypeError):
        return None


def _as_dt(unix):
    if unix is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(unix), tz=datetime.timezone.utc)
    except (ValueError, TypeError, OSError):
        return None
