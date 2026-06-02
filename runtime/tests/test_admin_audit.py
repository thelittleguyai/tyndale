"""Phase CO-9 Module 4 — admin audit-log viewer tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.db.base import AsyncSessionLocal
from app.db.models.users import User


async def _make_user() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        u = User(email=f"al{uuid.uuid4().hex[:10]}@example.com", user_type="user")
        s.add(u)
        await s.commit()
        return u.user_id


@pytest.mark.asyncio
async def test_audit_log_filters_by_target_user(client: AsyncClient):
    uid = await _make_user()
    await client.post(f"/v1/admin/users/{uid}/force-logout")  # writes audit user_id=uid
    r = await client.get(f"/v1/admin/audit-log?user_id={uid}")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert entries
    assert all(e["target_user_id"] == str(uid) for e in entries)


@pytest.mark.asyncio
async def test_audit_log_filters_by_action_type(client: AsyncClient):
    uid = await _make_user()
    await client.post(f"/v1/admin/users/{uid}/block", json={"reason": "x"})  # action=block
    await client.post(f"/v1/admin/users/{uid}/unblock")  # action=unblock
    r = await client.get(f"/v1/admin/audit-log?user_id={uid}&action_type=block")
    entries = r.json()["entries"]
    assert entries
    assert all(e["action"] == "block" for e in entries)


@pytest.mark.asyncio
async def test_audit_log_export_returns_full_result_set(client: AsyncClient):
    uid = await _make_user()
    await client.post(f"/v1/admin/users/{uid}/force-logout")
    exp = (await client.get(f"/v1/admin/audit-log/export?user_id={uid}")).json()
    assert exp["count"] >= 1
    assert any(e["target_user_id"] == str(uid) for e in exp["entries"])
    assert exp["filters"]["user_id"] == str(uid)
