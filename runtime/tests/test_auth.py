"""Phase 2K auth tests — the load-bearing security surface.

Covers: rate limiting (per-email + per-IP), magic-link single-use + replay +
expiry, match-on-verified-email (admin found / new-user default role), session
cookie attributes, logout invalidation, and the USE_REAL_AUTH=false dev
fallback.

Google OAuth's network call is monkeypatched (no live Google). SendGrid is the
dev-stub (no live send). Everything else exercises the real code paths against
the local Postgres.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.dev_user import DEV_USER_EMAIL, DEV_USER_ID
from app.auth.jwt import create_magic_link_token
from app.auth.rate_limit import magic_link_limiter
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.magic_link import MagicLinkConsumed
from app.db.models.users import User

_TEST_SECRET = "test-secret-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture
def real_auth(monkeypatch):
    """Turn on real auth with a test secret + localhost-friendly cookies, and
    reset the in-memory rate limiter so tests don't bleed into each other."""
    s = get_settings()
    monkeypatch.setattr(s, "use_real_auth", True)
    monkeypatch.setattr(s, "auth_secret", _TEST_SECRET)
    monkeypatch.setattr(s, "cookie_domain", "")  # attach to the test host
    monkeypatch.setattr(s, "cookie_secure", False)  # http test client
    magic_link_limiter.reset()
    yield s
    magic_link_limiter.reset()


async def _seed_user(
    email: str, user_type: str = "user", user_id: uuid.UUID | None = None
) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            return existing.user_id
        kwargs = {"email": email, "user_type": user_type, "service_consent": True, "improvement_consent": False}
        if user_id is not None:
            kwargs["user_id"] = user_id
        u = User(**kwargs)
        db.add(u)
        await db.flush()
        uid = u.user_id
        await db.commit()
        return uid


# ---------- rate limiting -----------------------------------------------------
@pytest.mark.asyncio
async def test_magic_link_request_rate_limited_per_email(client: AsyncClient, real_auth) -> None:
    email = "ratelimit-email@example.com"
    for i in range(real_auth.magic_link_rate_per_email_hour):
        r = await client.post("/v1/auth/magic-link-request", json={"email": email})
        assert r.status_code == 200, f"req {i}: {r.text}"
    r = await client.post("/v1/auth/magic-link-request", json={"email": email})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


@pytest.mark.asyncio
async def test_magic_link_request_rate_limited_per_ip(client: AsyncClient, real_auth, monkeypatch) -> None:
    monkeypatch.setattr(real_auth, "magic_link_rate_per_ip_hour", 3)
    magic_link_limiter.reset()
    # Distinct emails so the per-email limit never trips; the per-IP cap does.
    for i in range(3):
        r = await client.post("/v1/auth/magic-link-request", json={"email": f"ip{i}@example.com"})
        assert r.status_code == 200, r.text
    r = await client.post("/v1/auth/magic-link-request", json={"email": "ip-final@example.com"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


# ---------- magic-link single-use / replay / expiry ---------------------------
@pytest.mark.asyncio
async def test_magic_link_verify_consumes_jti_once(client: AsyncClient, real_auth) -> None:
    token, jti = create_magic_link_token("newcomer@example.com", None)
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert r.status_code == 302, r.text
    # session cookie set
    assert any("tyndale_session=" in h for h in r.headers.get_list("set-cookie"))
    # jti recorded as consumed
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(MagicLinkConsumed).where(MagicLinkConsumed.jti == jti)
        )).scalar_one_or_none()
    assert row is not None


@pytest.mark.asyncio
async def test_magic_link_verify_replay_returns_401(client: AsyncClient, real_auth) -> None:
    token, _ = create_magic_link_token("replay@example.com", None)
    first = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert first.status_code == 302
    second = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_magic_link_expired_token_returns_401(client: AsyncClient, real_auth, monkeypatch) -> None:
    # TTL in the past -> the freshly-minted token is already expired.
    monkeypatch.setattr(real_auth, "magic_link_ttl_minutes", -1)
    token, _ = create_magic_link_token("expired@example.com", None)
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert r.status_code == 401


# ---------- match-on-verified-email (via the OAuth callback) ------------------
@pytest.mark.asyncio
async def test_google_oauth_callback_match_on_verified_email_finds_admin(
    client: AsyncClient, real_auth, monkeypatch
) -> None:
    # Seed under the canonical DEV_USER_ID so the dev-fallback path (which keys
    # on that id) stays consistent across tests — mirrors the production seed.
    await _seed_user(DEV_USER_EMAIL, user_type="admin", user_id=DEV_USER_ID)

    async def fake_google(code: str) -> dict:
        return {"email": DEV_USER_EMAIL, "verified_email": True, "name": "Phil"}

    monkeypatch.setattr("app.routes.auth.handle_google_callback", fake_google)
    client.cookies.set("tyndale_oauth_state", "state123")
    r = await client.get("/v1/auth/callback?code=abc&state=state123", follow_redirects=False)
    assert r.status_code == 302, r.text

    # The session now resolves to the admin row (no new user created).
    me = await client.get("/v1/auth/session")
    assert me.status_code == 200, me.text
    assert me.json()["user"]["email"] == DEV_USER_EMAIL
    assert me.json()["user"]["user_type"] == "admin"


@pytest.mark.asyncio
async def test_google_oauth_callback_creates_new_user_default_role(
    client: AsyncClient, real_auth, monkeypatch
) -> None:
    new_email = f"new-{uuid.uuid4().hex[:8]}@example.com"

    async def fake_google(code: str) -> dict:
        return {"email": new_email, "verified_email": True, "name": "New User"}

    monkeypatch.setattr("app.routes.auth.handle_google_callback", fake_google)
    client.cookies.set("tyndale_oauth_state", "st")
    r = await client.get("/v1/auth/callback?code=abc&state=st", follow_redirects=False)
    assert r.status_code == 302
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.email == new_email))).scalar_one()
    assert u.user_type == "user"  # default role, never admin


@pytest.mark.asyncio
async def test_callback_rejects_state_mismatch(client: AsyncClient, real_auth) -> None:
    client.cookies.set("tyndale_oauth_state", "real-state")
    r = await client.get("/v1/auth/callback?code=abc&state=forged", follow_redirects=False)
    assert r.status_code == 400


# ---------- session cookie attributes + logout --------------------------------
@pytest.mark.asyncio
async def test_session_cookie_attributes(client: AsyncClient, real_auth, monkeypatch) -> None:
    # Force Secure on to confirm all three attributes appear together.
    monkeypatch.setattr(real_auth, "cookie_secure", True)
    token, _ = create_magic_link_token("cookie@example.com", None)
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    set_cookie = next(h for h in r.headers.get_list("set-cookie") if "tyndale_session=" in h)
    lowered = set_cookie.lower()
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=lax" in lowered


@pytest.mark.asyncio
async def test_session_invalidated_on_logout(client: AsyncClient, real_auth) -> None:
    token, _ = create_magic_link_token("logout@example.com", None)
    await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    # authenticated
    assert (await client.get("/v1/auth/session")).status_code == 200
    # logout clears the cookie
    out = await client.post("/v1/auth/logout")
    assert out.status_code == 200
    client.cookies.clear()  # browser would drop the expired cookie
    # now unauthenticated
    assert (await client.get("/v1/auth/session")).status_code == 401


@pytest.mark.asyncio
async def test_no_cookie_returns_401_under_real_auth(client: AsyncClient, real_auth) -> None:
    client.cookies.clear()
    assert (await client.get("/v1/auth/session")).status_code == 401


# ---------- dev-mode fallback (regression) ------------------------------------
@pytest.mark.asyncio
async def test_use_real_auth_false_returns_dev_user(client: AsyncClient) -> None:
    # Default conftest state: use_real_auth is false -> dev admin, no cookie.
    get_settings().use_real_auth = False
    r = await client.get("/v1/auth/session")
    assert r.status_code == 200, r.text
    assert r.json()["user"]["user_type"] == "admin"
