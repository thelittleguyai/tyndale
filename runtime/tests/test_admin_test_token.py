"""Dev-only, admin-only synthetic test-token endpoint (HP-2).

The e2e harness authenticates as a synthetic test user via an admin-issued token. These lock the
three gates: it mints a working token for a synthetic identity, rejects a real email, and 404s
in production. (The admin gate itself — 404 for non-admins — is covered by the shared admin_user
dependency; the dev test user is an admin, so these requests pass it.)"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.auth.jwt import verify_session_claims
from app.config import get_settings

_SYNTH = "e2e-clean-bill@e2e.tyndale.test"


@pytest.mark.asyncio
async def test_mints_a_working_token_for_a_synthetic_user(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", "x" * 32)  # session signing needs a secret
    r = await client.post("/v1/admin/test-token", json={"email": _SYNTH})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == _SYNTH
    assert body["cookie_name"]  # the driver needs the cookie name to set the session
    uid, _version = verify_session_claims(body["token"])  # the token really verifies…
    assert uid == body["user_id"]  # …to the synthetic user it minted


@pytest.mark.asyncio
async def test_rejects_a_non_synthetic_email(client: AsyncClient):
    r = await client.post("/v1/admin/test-token", json={"email": "someone@gmail.com"})
    assert r.status_code == 400  # a token can NEVER be minted for a real user here


@pytest.mark.asyncio
async def test_404s_in_production(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "node_env", "production")
    r = await client.post("/v1/admin/test-token", json={"email": _SYNTH})
    assert r.status_code == 404  # the endpoint effectively does not exist in prod
