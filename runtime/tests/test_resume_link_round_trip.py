"""The resume path re-issues a fresh link cleanly (Brock 2026-09-21, decision 7).

A guided intake is saved as the user goes; they leave to find a document and come back with a
sign-in link that works for 15 minutes (the resume copy says so). Two things had to be true
and neither was:

  * an EXPIRED link answered with a JSON 401 on the API host — now it lands on the app's
    sign-in screen, which renews it in one tap (the address rides inside the signed token);
  * after signing in, a user with a guided case left unfinished landed on the dashboard — now
    the sign-in lands on /intake at the planner's next screen. (A bare return path also
    resolved against the API host — api.tyndaleapp.net/case/… — not the app.)
"""

from __future__ import annotations

import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.jwt import create_magic_link_token
from app.auth.rate_limit import magic_link_limiter
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.users import User

_SECRET = "test-secret-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture
def real_auth(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "use_real_auth", True)
    monkeypatch.setattr(s, "auth_secret", _SECRET)
    monkeypatch.setattr(s, "cookie_domain", "")
    monkeypatch.setattr(s, "cookie_secure", False)
    monkeypatch.setattr(s, "auth_success_redirect", "https://app.example.test")
    monkeypatch.setattr(s, "magic_link_base_url", "https://api.example.test")
    magic_link_limiter.reset()
    yield s
    magic_link_limiter.reset()


@pytest.fixture
def outbox(monkeypatch):
    sent: list[tuple[str, str]] = []

    async def capture(email, url):
        sent.append((email, url))

    monkeypatch.setattr("app.routes.auth.send_magic_link_email", capture)
    return sent


def _token_of(url: str) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["t" if "t=" in url else "token"][0]


async def _user_with_unfinished_guided_case(email: str) -> tuple[uuid.UUID, str]:
    async with AsyncSessionLocal() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if u is None:
            u = User(email=email, user_type="user", service_consent=True, improvement_consent=False,
                     intake_mode="guided", intake_cohort="guided")
            s.add(u)
            await s.flush()
        cf = CaseFile(user_id=u.user_id, status="open", intake_mode="guided", intake_status="in_progress",
                      documents=[], intake_state={"acked": ["welcome"]})
        s.add(cf)
        await s.commit()
        return u.user_id, str(cf.case_file_id)


@pytest.mark.asyncio
async def test_an_expired_link_renews_and_the_sign_in_resumes_the_intake(client: AsyncClient, real_auth, outbox, monkeypatch):
    email = f"resumer-{uuid.uuid4().hex[:8]}@example.com"
    _, case_id = await _user_with_unfinished_guided_case(email)

    # the link they came back with is past its 15 minutes
    monkeypatch.setattr(real_auth, "magic_link_ttl_minutes", -1)
    stale, _ = create_magic_link_token(email, None)
    monkeypatch.setattr(real_auth, "magic_link_ttl_minutes", 15)
    r = await client.get(f"/v1/auth/magic-link-verify?token={stale}", follow_redirects=False)
    assert r.status_code == 302
    where = r.headers["location"]
    assert where.startswith("https://app.example.test/sign-in?") and "link=expired" in where
    assert not any("tyndale_session=" in h for h in r.headers.get_list("set-cookie"))

    # the app's one tap: renew it — the address comes from the token, nobody retypes it
    renew = await client.post("/v1/auth/magic-link-reissue", json={"token": _token_of(where)})
    assert renew.status_code == 200, renew.text
    assert renew.json()["email_hint"] == "r•••@example.com"
    (to, fresh_url), = outbox
    assert to == email and fresh_url.startswith("https://api.example.test/v1/auth/magic-link-verify?token=")

    # the fresh link signs them in … on the intake, at the planner's next screen
    r = await client.get(fresh_url.replace("https://api.example.test", ""), follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"https://app.example.test/intake?case={case_id}"
    cookie = next(h for h in r.headers.get_list("set-cookie") if h.startswith("tyndale_session="))
    client.cookies.set("tyndale_session", cookie.split(";")[0].split("=", 1)[1])
    state = (await client.get("/v1/intake/state", params={"case_file_id": case_id})).json()
    assert state["case_file_id"] == case_id and state["current_step"] not in ("READY", None)


@pytest.mark.asyncio
async def test_an_explicit_return_path_survives_the_renewal(client: AsyncClient, real_auth, outbox, monkeypatch):
    monkeypatch.setattr(real_auth, "magic_link_ttl_minutes", -1)
    stale, _ = create_magic_link_token("returner-2@example.com", "/intake?case=abc&screen=eob")
    monkeypatch.setattr(real_auth, "magic_link_ttl_minutes", 15)
    assert (await client.post("/v1/auth/magic-link-reissue", json={"token": stale})).status_code == 200
    (_, fresh_url), = outbox
    r = await client.get(fresh_url.replace("https://api.example.test", ""), follow_redirects=False)
    assert r.headers["location"] == "https://app.example.test/intake?case=abc&screen=eob"


@pytest.mark.asyncio
async def test_only_an_authentic_recently_expired_link_can_be_renewed(client: AsyncClient, real_auth, outbox):
    live, _ = create_magic_link_token("live@example.com", None)
    assert (await client.post("/v1/auth/magic-link-reissue", json={"token": live})).status_code == 400  # just use it
    forged = pyjwt.encode({"email": "victim@example.com", "jti": "x", "iss": "tyndale", "aud": "magic_link",
                           "iat": datetime.now(timezone.utc) - timedelta(hours=1),
                           "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
                          "not-the-secret", algorithm="HS256")
    assert (await client.post("/v1/auth/magic-link-reissue", json={"token": forged})).status_code == 400
    ancient = pyjwt.encode({"email": "old@example.com", "jti": "y", "iss": "tyndale", "aud": "magic_link",
                            "iat": datetime.now(timezone.utc) - timedelta(days=30),
                            "exp": datetime.now(timezone.utc) - timedelta(days=29)},
                           _SECRET, algorithm="HS256")
    assert (await client.post("/v1/auth/magic-link-reissue", json={"token": ancient})).status_code == 400
    assert outbox == []


@pytest.mark.asyncio
async def test_a_sign_in_with_nothing_unfinished_lands_where_it_always_did(client: AsyncClient, real_auth):
    token, _ = create_magic_link_token(f"plain-{uuid.uuid4().hex[:8]}@example.com", None)
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert r.headers["location"] == "https://app.example.test"
