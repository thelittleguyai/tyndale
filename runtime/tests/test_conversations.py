"""Phase CO-10 — conversation CRUD routes."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.auth import CurrentUser, current_user
from app.auth.dev_user import DEV_USER_ID
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.messages import Message
from app.main import app


async def _make_case() -> str:
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=DEV_USER_ID, status="open")
        s.add(cf)
        await s.commit()
        await s.refresh(cf)
        return str(cf.case_file_id)


async def test_create_conversation_per_case_links_to_case_id(client: AsyncClient):
    case_id = await _make_case()
    r = await client.post("/v1/conversations", json={"case_id": case_id})
    assert r.status_code == 201
    body = r.json()
    assert body["case_id"] == case_id
    assert body["mode"] == "per_case"
    assert body["title"] is None


async def test_create_conversation_freeform_case_id_is_null(client: AsyncClient):
    r = await client.post("/v1/conversations", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["case_id"] is None
    assert body["mode"] == "freeform"


async def test_list_conversations_paginates_and_filters_by_mode(client: AsyncClient):
    case_id = await _make_case()
    await client.post("/v1/conversations", json={"case_id": case_id})
    await client.post("/v1/conversations", json={})

    r = await client.get("/v1/conversations", params={"mode": "freeform", "limit": 100})
    assert r.status_code == 200
    data = r.json()
    assert data["limit"] == 100 and "total" in data
    assert all(c["case_id"] is None for c in data["conversations"])

    r2 = await client.get("/v1/conversations", params={"mode": "per_case", "limit": 100})
    assert all(c["case_id"] is not None for c in r2.json()["conversations"])


async def test_get_conversation_returns_ordered_messages(client: AsyncClient):
    cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
    async with AsyncSessionLocal() as s:
        s.add(Message(conversation_id=uuid.UUID(cid), sequence_number=2, role="assistant", content="a2", status="complete"))
        s.add(Message(conversation_id=uuid.UUID(cid), sequence_number=1, role="user", content="u1", status="complete"))
        await s.commit()
    r = await client.get(f"/v1/conversations/{cid}")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["sequence_number"] for m in msgs] == [1, 2]
    assert msgs[0]["role"] == "user"


async def test_patch_conversation_updates_title_and_archived(client: AsyncClient):
    cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
    r = await client.patch(
        f"/v1/conversations/{cid}", json={"title": "My title", "is_archived": True}
    )
    assert r.status_code == 200
    assert r.json()["title"] == "My title"
    assert r.json()["is_archived"] is True


async def test_delete_conversation_soft_deletes(client: AsyncClient):
    cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
    r = await client.delete(f"/v1/conversations/{cid}")
    assert r.status_code == 204
    got = await client.get(f"/v1/conversations/{cid}")
    assert got.json()["is_archived"] is True  # still retrievable, just archived
    lst = await client.get("/v1/conversations")  # excluded from default list
    assert cid not in [c["conversation_id"] for c in lst.json()["conversations"]]


async def test_non_owner_user_returns_403(client: AsyncClient):
    cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
    other = CurrentUser(
        user_id=uuid.uuid4(), email="other@example.com", first_name="O", user_type="user"
    )
    app.dependency_overrides[current_user] = lambda: other
    try:
        r = await client.get(f"/v1/conversations/{cid}")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(current_user, None)
