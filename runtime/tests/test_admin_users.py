"""Phase CO-9 Module 1 — admin user management route tests.

The seeded dev user is admin, so `client` is admin. Target users are created directly.
The blocked/soft-deleted/stale-JWT enforcement is unit-tested via enforce_user_access
(the dev-user auth path bypasses it, so we exercise the function directly).
"""

from __future__ import annotations

import datetime
import json
import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.auth import current_user
from app.auth.current_user import enforce_user_access
from app.auth.dev_user import CurrentUser, resolve_dev_user
from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.main import app


async def _dev_admin_id() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _make_user(email: str | None = None, user_type: str = "user") -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        u = User(email=email or f"u{uuid.uuid4().hex[:10]}@example.com", user_type=user_type)
        s.add(u)
        await s.commit()
        return u.user_id


async def _get_user(uid: uuid.UUID) -> User:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(User).where(User.user_id == uid))).scalar_one()


async def _audit_for(uid: uuid.UUID) -> list[AuditEvent]:
    async with AsyncSessionLocal() as s:
        return list(
            (await s.execute(select(AuditEvent).where(AuditEvent.user_id == uid))).scalars().all()
        )


def _action(ev: AuditEvent) -> str | None:
    return json.loads(bytes(ev.payload_encrypted).decode()).get("action")


@pytest.fixture
def as_non_admin():
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=uuid.uuid4(), email="regular@example.com", first_name="Reg", user_type="user"
    )
    yield
    app.dependency_overrides.pop(current_user, None)


# --------------------------------------------------------------------------- #
# List + DL-60 gate
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_users_paginates_and_filters_by_status(client: AsyncClient):
    bid = await _make_user()
    await client.post(f"/v1/admin/users/{bid}/block", json={"reason": "x"})

    r = await client.get("/v1/admin/users?status=active&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] <= 5
    assert all(u["status"] == "active" for u in body["users"])

    blocked = (await client.get("/v1/admin/users?status=blocked")).json()
    assert any(u["user_id"] == str(bid) for u in blocked["users"])
    assert all(u["status"] == "blocked" for u in blocked["users"])


@pytest.mark.asyncio
async def test_non_admin_user_calling_admin_endpoint_returns_404(client: AsyncClient, as_non_admin):
    # DL-60 anti-enumeration: non-admin → 404, NOT 403.
    assert (await client.get("/v1/admin/users")).status_code == 404


# --------------------------------------------------------------------------- #
# Block / unblock
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_block_sets_flag_bumps_jwt_version_writes_audit(client: AsyncClient):
    uid = await _make_user()
    assert (await _get_user(uid)).jwt_version == 1
    r = await client.post(f"/v1/admin/users/{uid}/block", json={"reason": "abuse"})
    assert r.status_code == 200, r.text
    u = await _get_user(uid)
    assert u.is_blocked is True
    assert u.blocked_reason == "abuse"
    assert u.blocked_by is not None
    assert u.jwt_version == 2  # bumped → outstanding sessions revoked
    audits = await _audit_for(uid)
    # MEDIUM-5 (2026-08-19): actor is the acting admin's UUID; email lives in the payload.
    assert any(_action(a) == "block" and uuid.UUID(a.actor) for a in audits)


@pytest.mark.asyncio
async def test_unblock_clears_flag_writes_audit_no_jwt_bump(client: AsyncClient):
    uid = await _make_user()
    await client.post(f"/v1/admin/users/{uid}/block", json={"reason": "x"})
    v = (await _get_user(uid)).jwt_version  # == 2
    r = await client.post(f"/v1/admin/users/{uid}/unblock")
    assert r.status_code == 200
    u = await _get_user(uid)
    assert u.is_blocked is False and u.blocked_reason is None
    assert u.jwt_version == v  # NO bump on unblock
    assert any(_action(a) == "unblock" for a in await _audit_for(uid))


# --------------------------------------------------------------------------- #
# Reset onboarding / force logout
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_reset_onboarding_sets_intake_to_not_started_bumps_jwt(client: AsyncClient):
    uid = await _make_user()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status="open", intake_status="complete")
        s.add(cf)
        await s.commit()
        cfid = cf.case_file_id
    v = (await _get_user(uid)).jwt_version
    r = await client.post(f"/v1/admin/users/{uid}/reset-onboarding")
    assert r.status_code == 200
    assert (await _get_user(uid)).jwt_version == v + 1
    async with AsyncSessionLocal() as s:
        cf2 = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cfid))).scalar_one()
    assert cf2.intake_status == "not_started"


@pytest.mark.asyncio
async def test_force_logout_bumps_jwt_version(client: AsyncClient):
    uid = await _make_user()
    v = (await _get_user(uid)).jwt_version
    r = await client.post(f"/v1/admin/users/{uid}/force-logout")
    assert r.status_code == 200
    assert (await _get_user(uid)).jwt_version == v + 1


# --------------------------------------------------------------------------- #
# Magic link / soft delete
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_send_magic_link_invokes_sender(client: AsyncClient, monkeypatch):
    captured: dict = {}

    async def _fake_send(email: str, url: str) -> None:
        captured["email"] = email
        captured["url"] = url

    monkeypatch.setattr("app.routes.admin.users.send_magic_link_email", _fake_send)
    # Magic-link token signing needs an AUTH_SECRET (not set in the default test env).
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "auth_secret", "x" * 32)  # has_real_auth_secret() then passes
    email = f"ml{uuid.uuid4().hex[:8]}@example.com"
    uid = await _make_user(email=email)
    r = await client.post(f"/v1/admin/users/{uid}/send-magic-link")
    assert r.status_code == 200
    assert captured["email"] == email
    assert "magic-link-verify?token=" in captured["url"]  # token only, no PHI (DL-47)
    assert any(_action(a) == "send_magic_link" for a in await _audit_for(uid))


@pytest.mark.asyncio
async def test_soft_delete_anonymizes_email_preserves_audit_trail(client: AsyncClient):
    email = f"sd{uuid.uuid4().hex[:8]}@example.com"
    uid = await _make_user(email=email)
    await client.post(f"/v1/admin/users/{uid}/force-logout")  # seed an audit row
    r = await client.post(f"/v1/admin/users/{uid}/soft-delete")
    assert r.status_code == 200
    u = await _get_user(uid)
    assert u.soft_deleted_at is not None and u.soft_deleted_by is not None
    assert u.email.startswith("deleted-") and u.email.endswith("@deleted.tyndaleapp.net")
    assert u.email != email
    assert u.user_id == uid  # user_id preserved
    audits = await _audit_for(uid)  # audit trail preserved (force_logout + soft_delete)
    assert len(audits) >= 2
    assert any(_action(a) == "soft_delete" for a in audits)


# --------------------------------------------------------------------------- #
# Set-role admin toggle (CO-9 addition)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_set_role_toggles_admin(client: AsyncClient):
    uid = await _make_user(user_type="user")
    r = await client.post(f"/v1/admin/users/{uid}/set-role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["user_type"] == "admin"
    assert (await _get_user(uid)).user_type == "admin"
    await client.post(f"/v1/admin/users/{uid}/set-role", json={"role": "user"})
    assert (await _get_user(uid)).user_type == "user"
    assert any(_action(a) == "set_role" for a in await _audit_for(uid))


@pytest.mark.asyncio
async def test_set_role_cannot_self_demote(client: AsyncClient):
    admin_id = await _dev_admin_id()
    r = await client.post(f"/v1/admin/users/{admin_id}/set-role", json={"role": "user"})
    assert r.status_code == 400  # self-lockout guard
    assert (await _get_user(admin_id)).user_type == "admin"


# --------------------------------------------------------------------------- #
# enforce_user_access (security property, unit)
# --------------------------------------------------------------------------- #
def test_blocked_user_access_raises_403():
    u = User(is_blocked=True, blocked_reason="abuse", soft_deleted_at=None, jwt_version=1)
    with pytest.raises(HTTPException) as e:
        enforce_user_access(u, 1)
    assert e.value.status_code == 403 and e.value.detail["code"] == "USER_BLOCKED"


def test_soft_deleted_user_access_raises_401():
    u = User(is_blocked=False, soft_deleted_at=datetime.datetime.now(datetime.timezone.utc))
    with pytest.raises(HTTPException) as e:
        enforce_user_access(u, 1)
    assert e.value.status_code == 401 and e.value.detail["code"] == "USER_DELETED"


def test_jwt_with_stale_version_returns_401():
    u = User(is_blocked=False, soft_deleted_at=None, jwt_version=3)
    with pytest.raises(HTTPException) as e:
        enforce_user_access(u, 1)  # token ver 1 < user ver 3
    assert e.value.status_code == 401 and e.value.detail["code"] == "JWT_INVALIDATED"
