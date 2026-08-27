"""Stripe webhook idempotency (audit 2026-08-27 item 6): a redelivered event id is a
logged no-op — subscription state is applied exactly once."""

import hashlib
import hmac
import json
import time
import uuid

import pytest
from httpx import AsyncClient


def _sign(payload: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


@pytest.mark.asyncio
async def test_duplicate_event_id_applies_once(client: AsyncClient, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_billing", True, raising=False)
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test", raising=False)

    applied = []

    async def fake_apply(session, **state):
        applied.append(state)

    import app.routes.billing as billing_route

    monkeypatch.setattr(billing_route, "apply_subscription_state", fake_apply)

    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": str(uuid.uuid4()), "customer": "cus_x", "subscription": "sub_x"}},
    }
    body = json.dumps(event).encode()
    sig = _sign(body, "whsec_test")
    for _ in range(2):
        r = await client.post(
            "/v1/billing/webhook", content=body,
            headers={"Stripe-Signature": sig, "Content-Type": "application/json"},
        )
        assert r.status_code == 200, r.text
    assert len(applied) == 1  # second delivery was the logged no-op
