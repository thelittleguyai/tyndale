"""Phase 2K.2 runtime-hardening tests.

Covers rate limiting (per-IP, per-user, per-route), security headers, request +
upload size limits, error-response hardening, JWT algorithm/audience/required-
claim validation, CORS posture, the __Secure- cookie name + legacy grace
period, the PHI log filter, and unauthenticated anti-enumeration.

Rate limiting is OFF by default in the suite (conftest sets RATE_LIMIT_ENABLED=
false); the fixtures here flip it on per-test and reset the shared limiter.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.jwt import (
    InvalidTokenError,
    create_magic_link_token,
    create_session_token,
    verify_session_token,
)
from app.auth.rate_limit import magic_link_limiter
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.users import User
from app.main import create_app
from app.middleware.phi_log_filter import scrub
from app.middleware.rate_limit import global_limiter

_TEST_SECRET = "test-secret-hardening-aaaaaaaaaaaaaaaaaaaaaaaaaa"


# --- fixtures ----------------------------------------------------------------
@pytest.fixture
def real_auth(monkeypatch):
    """Real auth on, localhost-friendly cookies, a usable AUTH_SECRET, and both
    in-memory limiters cleared so tests don't bleed into each other."""
    s = get_settings()
    monkeypatch.setattr(s, "use_real_auth", True)
    monkeypatch.setattr(s, "auth_secret", _TEST_SECRET)
    monkeypatch.setattr(s, "cookie_domain", "")
    monkeypatch.setattr(s, "cookie_secure", False)
    magic_link_limiter.reset()
    global_limiter.reset()
    yield s
    magic_link_limiter.reset()
    global_limiter.reset()


@pytest.fixture
def rate_on(monkeypatch):
    """Turn the global rate limiter on (it's off in the rest of the suite)."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", True)
    global_limiter.reset()
    yield s
    global_limiter.reset()


async def _seed_user(email: str, user_type: str = "user") -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            return existing.user_id
        u = User(email=email, user_type=user_type, service_consent=True, improvement_consent=False)
        db.add(u)
        await db.flush()
        uid = u.user_id
        await db.commit()
        return uid


# --- rate limiting -----------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limit_per_ip_baseline_429s_on_overflow(client, rate_on, monkeypatch):
    monkeypatch.setattr(rate_on, "rate_limit_per_ip_per_minute", 3)
    monkeypatch.setattr(rate_on, "rate_limit_per_ip_per_hour", 1000)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    for i in range(3):
        r = await client.get("/v1/auth/session", headers=headers)
        assert r.status_code != 429, f"req {i}: {r.status_code}"
    r = await client.get("/v1/auth/session", headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


@pytest.mark.asyncio
async def test_rate_limit_per_user_baseline_429s_on_overflow(client, real_auth, monkeypatch):
    monkeypatch.setattr(real_auth, "rate_limit_enabled", True)
    monkeypatch.setattr(real_auth, "rate_limit_per_user_per_minute", 3)
    monkeypatch.setattr(real_auth, "rate_limit_per_ip_per_minute", 1000)
    monkeypatch.setattr(real_auth, "rate_limit_per_ip_per_hour", 1000)
    global_limiter.reset()
    uid = await _seed_user("rluser@example.com")
    client.cookies.set("tyndale_session", create_session_token(str(uid)))
    headers = {"X-Forwarded-For": "203.0.113.8"}
    for i in range(3):
        r = await client.get("/v1/auth/session", headers=headers)
        assert r.status_code == 200, f"req {i}: {r.status_code} {r.text}"
    r = await client.get("/v1/auth/session", headers=headers)
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_per_route_upload_caps_at_20_per_hour(client, rate_on, monkeypatch):
    monkeypatch.setattr(rate_on, "rate_limit_upload_per_hour", 1)
    monkeypatch.setattr(rate_on, "rate_limit_per_ip_per_minute", 1000)
    monkeypatch.setattr(rate_on, "rate_limit_per_ip_per_hour", 1000)
    r1 = await client.post(
        "/v1/upload", files={"file": ("bill.txt", b"STUB OCR - x", "text/plain")}
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        "/v1/upload", files={"file": ("bill.txt", b"STUB OCR - x", "text/plain")}
    )
    assert r2.status_code == 429


# --- security headers --------------------------------------------------------
@pytest.mark.asyncio
async def test_security_headers_present_on_all_responses(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "max-age=31536000" in r.headers.get("strict-transport-security", "")
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in r.headers.get("permissions-policy", "")


# --- request / upload size limits --------------------------------------------
@pytest.mark.asyncio
async def test_request_body_size_limit_413s_on_overflow(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_json_body_bytes", 10)
    r = await client.post("/v1/auth/magic-link-request", json={"email": "someone@example.com"})
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


@pytest.mark.asyncio
async def test_upload_file_size_limit_413s(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_file_bytes", 8)
    files = {"file": ("bill.txt", b"this is definitely more than eight bytes", "text/plain")}
    r = await client.post("/v1/upload", files=files)
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_card_upload_uses_larger_upload_cap(client, monkeypatch):
    """CO-18: the insurance-card upload path uses max_upload_body_bytes, so a base64
    card payload that exceeds the tiny JSON cap still passes the middleware to the route."""
    import base64

    monkeypatch.setattr(get_settings(), "max_json_body_bytes", 10)
    img = base64.b64encode(b"\x89PNG fake insurance card image bytes").decode()
    r = await client.post(
        "/v1/insurance/card/upload",
        json={"card_type": "front", "image_base64": img, "mime_type": "image/png"},
    )
    assert r.status_code == 200, r.text  # not a middleware 413 — it reached the route


@pytest.mark.asyncio
async def test_card_upload_over_upload_cap_413s(client, monkeypatch):
    """CO-18: a card body over max_upload_body_bytes is still rejected by the middleware."""
    import base64

    monkeypatch.setattr(get_settings(), "max_upload_body_bytes", 10)
    img = base64.b64encode(b"a body that is definitely more than ten bytes once encoded").decode()
    r = await client.post(
        "/v1/insurance/card/upload",
        json={"card_type": "front", "image_base64": img, "mime_type": "image/png"},
    )
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


@pytest.mark.asyncio
async def test_non_upload_json_cap_unchanged(client, monkeypatch):
    """CO-18: the 1 MB JSON cap is unchanged for non-upload paths."""
    monkeypatch.setattr(get_settings(), "max_json_body_bytes", 10)
    r = await client.post("/v1/auth/magic-link-request", json={"email": "someone@example.com"})
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


# --- error-response hardening ------------------------------------------------
def _app_that_raises():
    from fastapi import FastAPI

    from app.middleware.error_handler import add_error_handlers

    a = FastAPI()
    add_error_handlers(a)

    @a.get("/boom")
    async def boom():  # noqa: ANN202
        raise RuntimeError("secret-detail-xyz")

    return a


@pytest.mark.asyncio
async def test_error_response_no_traceback_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "node_env", "production")
    transport = ASGITransport(app=_app_that_raises(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert "traceback" not in body
    assert "secret-detail-xyz" not in str(body)  # exception message not leaked
    assert body["correlation_id"]


@pytest.mark.asyncio
async def test_error_response_includes_correlation_id(monkeypatch):
    monkeypatch.setattr(get_settings(), "node_env", "development")
    transport = ASGITransport(app=_app_that_raises(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["correlation_id"] and body["request_id"]
    assert "traceback" in body  # dev surfaces it


# --- JWT hardening -----------------------------------------------------------
def test_jwt_algorithm_confusion_rejected(real_auth):
    iat = datetime.now(timezone.utc)
    payload = {
        "sub": "u",
        "iss": "tyndale",
        "aud": "session",
        "iat": iat,
        "exp": iat + timedelta(hours=1),
    }
    unsigned = pyjwt.encode(payload, key="", algorithm="none")
    with pytest.raises(InvalidTokenError):
        verify_session_token(unsigned)


def test_jwt_audience_mismatch_rejected(real_auth):
    magic_token, _jti = create_magic_link_token("x@example.com", None)
    with pytest.raises(InvalidTokenError):
        verify_session_token(magic_token)  # magic-link aud presented as a session


def test_jwt_missing_required_claim_rejected(real_auth):
    iat = datetime.now(timezone.utc)
    payload = {
        "iss": "tyndale",
        "aud": "session",
        "iat": iat,
        "exp": iat + timedelta(hours=1),
    }  # no sub
    token = pyjwt.encode(payload, _TEST_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        verify_session_token(token)


# --- CORS posture ------------------------------------------------------------
@pytest.mark.asyncio
async def test_cors_rejects_unauthorized_origin(client):
    r = await client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"


@pytest.mark.asyncio
async def test_cors_allows_authorized_origins_with_credentials(client):
    r = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert r.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_allows_dev_and_app_origins(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(
        s, "cors_allowed_origins", "https://dev.tyndaleapp.net,https://app.tyndaleapp.net"
    )
    monkeypatch.setattr(s, "node_env", "production")  # no localhost added in prod
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        for origin in ("https://dev.tyndaleapp.net", "https://app.tyndaleapp.net"):
            r = await c.get("/health", headers={"Origin": origin})
            assert r.headers.get("access-control-allow-origin") == origin
            assert r.headers.get("access-control-allow-credentials") == "true"
        r = await c.get("/health", headers={"Origin": "https://evil.example.com"})
        assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"


# --- cookie __Secure- prefix + legacy grace ----------------------------------
@pytest.mark.asyncio
async def test_secure_cookie_name_used(client, real_auth, monkeypatch):
    monkeypatch.setattr(real_auth, "cookie_secure", True)  # → __Secure- prefix
    token, _ = create_magic_link_token("cookieuser@example.com", None)
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert r.status_code == 302, r.text
    set_cookie = next(h for h in r.headers.get_list("set-cookie") if "tyndale_session=" in h)
    assert "__Secure-tyndale_session=" in set_cookie


@pytest.mark.asyncio
async def test_legacy_cookie_name_accepted_for_grace_period(client, real_auth, monkeypatch):
    monkeypatch.setattr(real_auth, "cookie_secure", True)  # write __Secure-; still READ legacy
    uid = await _seed_user("legacy@example.com")
    client.cookies.set("tyndale_session", create_session_token(str(uid)))  # the LEGACY name
    r = await client.get("/v1/auth/session")
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == "legacy@example.com"


# --- PHI log filter ----------------------------------------------------------
def test_phi_log_filter_scrubs_ssn_pattern():
    out = scrub("patient SSN is 123-45-6789 on file")
    assert "123-45-6789" not in out
    assert "[REDACTED]" in out


def test_phi_log_filter_scrubs_dollar_paired_with_identifier():
    out = scrub("provider billed $1,250.00 on claim #44982 last week")
    assert "[REDACTED]" in out
    assert "44982" not in out


# --- anti-enumeration --------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthenticated_user_me_returns_401(client, real_auth):
    client.cookies.clear()
    r = await client.get("/v1/user/me")
    assert r.status_code == 401
    # Generic — never leaks whether the requester has an account.
    assert r.json()["detail"] == "not authenticated"
