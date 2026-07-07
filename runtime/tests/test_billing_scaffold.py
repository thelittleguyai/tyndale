"""Billing dark scaffold (Item 4, DL-16).

The whole feature is inert while enable_billing is False: routes 404, the audit-gate dependency is
a pure no-op, status reports disabled, and no billing row is ever written. Flag ON, the gate
enforces one free analysis then requires a subscription, and the webhook is signature-verified.
Stripe only ever receives the user UUID (DL-49)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth import CurrentUser
from app.billing.stripe_gateway import verify_webhook_signature
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.billing_accounts import BillingAccount
from app.db.models.users import User
from app.routes.billing import require_active_subscription_or_free_slot


async def _fresh_user() -> uuid.UUID:
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add(User(user_id=uid, email=f"billing-{uid.hex[:8]}@e2e.tyndale.test", user_type="user"))
        await s.commit()
    return uid


def _cu(uid: uuid.UUID) -> CurrentUser:
    return CurrentUser(user_id=uid, email="x@e2e.tyndale.test", first_name="x", user_type="user")


# --- flag OFF: the dark scaffold is completely inert -------------------------
@pytest.mark.asyncio
async def test_disabled_routes_404(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_billing", False)
    assert (await client.post("/v1/billing/checkout", json={"plan": "monthly"})).status_code == 404
    assert (await client.post("/v1/billing/webhook", content=b"{}")).status_code == 404


@pytest.mark.asyncio
async def test_disabled_status_reports_disabled(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_billing", False)
    r = await client.get("/v1/billing/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


@pytest.mark.asyncio
async def test_disabled_gate_is_a_noop_and_writes_nothing(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_billing", False)
    uid = await _fresh_user()
    async with AsyncSessionLocal() as s:
        # Must not raise and must not create a billing row while disabled.
        await require_active_subscription_or_free_slot(user=_cu(uid), session=s)
    async with AsyncSessionLocal() as s:
        acct = (
            await s.execute(select(BillingAccount).where(BillingAccount.user_id == uid))
        ).scalar_one_or_none()
        assert acct is None  # dark scaffold never touches the ledger


# --- flag ON: the gate enforces one free analysis then a subscription --------
@pytest.mark.asyncio
async def test_enabled_gate_free_then_blocks_then_subscription(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "enable_billing", True)
    monkeypatch.setattr(s, "billing_free_analysis_limit", 1)
    uid = await _fresh_user()

    # 1st audit: the one free analysis is granted.
    async with AsyncSessionLocal() as sess:
        await require_active_subscription_or_free_slot(user=_cu(uid), session=sess)
    # 2nd audit: free slot spent, no subscription -> 402.
    with pytest.raises(Exception) as ei:
        async with AsyncSessionLocal() as sess:
            await require_active_subscription_or_free_slot(user=_cu(uid), session=sess)
    assert getattr(ei.value, "status_code", None) == 402

    # An active subscription lifts the cap.
    async with AsyncSessionLocal() as sess:
        acct = (
            await sess.execute(select(BillingAccount).where(BillingAccount.user_id == uid))
        ).scalar_one()
        acct.status = "active"
        await sess.commit()
    async with AsyncSessionLocal() as sess:
        await require_active_subscription_or_free_slot(user=_cu(uid), session=sess)  # no raise


@pytest.mark.asyncio
async def test_enabled_status_shape(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_billing", True)
    r = await client.get("/v1/billing/status")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["active"] is False
    assert "free_analyses_remaining" in body


# --- webhook signature verification ------------------------------------------
def _sign(payload: bytes, secret: str) -> str:
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


def test_verify_webhook_signature_unit(monkeypatch):
    secret = "whsec_test_123"
    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", secret)
    payload = b'{"hello":"world"}'
    assert verify_webhook_signature(payload, _sign(payload, secret)) is True
    assert verify_webhook_signature(payload, "t=1,v1=deadbeef") is False  # bad sig / stale ts
    assert verify_webhook_signature(payload, None) is False


@pytest.mark.asyncio
async def test_webhook_applies_subscription_on_valid_signature(client: AsyncClient, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "enable_billing", True)
    monkeypatch.setattr(s, "stripe_webhook_secret", "whsec_test_123")
    uid = await _fresh_user()

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": str(uid), "customer": "cus_1", "subscription": "sub_1"}},
    }
    payload = json.dumps(event).encode()

    bad = await client.post("/v1/billing/webhook", content=payload, headers={"Stripe-Signature": "t=1,v1=nope"})
    assert bad.status_code == 400  # invalid signature rejected

    good = await client.post(
        "/v1/billing/webhook", content=payload,
        headers={"Stripe-Signature": _sign(payload, "whsec_test_123")},
    )
    assert good.status_code == 200, good.text
    async with AsyncSessionLocal() as sess:
        acct = (
            await sess.execute(select(BillingAccount).where(BillingAccount.user_id == uid))
        ).scalar_one()
        assert acct.status == "active"
        assert acct.stripe_customer_id == "cus_1"
        assert acct.stripe_subscription_id == "sub_1"
