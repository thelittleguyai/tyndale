"""Phase CO-10 — streaming message route (SSE), modes, caps, stop, title, gaps.

All runs on the fixture stream (use_real_claude=False), so the SSE contract +
persistence are deterministic. Cap tests use a fresh isolated user so their
seeded rows don't pollute the shared dev user's rolling counts.
"""

from __future__ import annotations

import json
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.auth import CurrentUser, current_user
from app.auth.dev_user import DEV_USER_ID
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.knowledge_gap_log import KnowledgeGapLog
from app.db.models.messages import Message
from app.db.models.users import User
from app.main import app


async def _new_conversation(client: AsyncClient, case_id: str | None = None) -> str:
    body = {"case_id": case_id} if case_id else {}
    return (await client.post("/v1/conversations", json=body)).json()["conversation_id"]


async def _stream(client: AsyncClient, cid: str, content: str):
    """POST a message; return (status, json_or_None, events)."""
    events: list[dict] = []
    async with client.stream(
        "POST", f"/v1/conversations/{cid}/messages", json={"content": content}
    ) as resp:
        if resp.status_code != 200:
            raw = await resp.aread()
            return resp.status_code, json.loads(raw), events
        cur: dict = {}
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                cur = {"event": line.split(":", 1)[1].strip()}
            elif line.startswith("data:"):
                cur["data"] = json.loads(line.split(":", 1)[1].strip())
                events.append(cur)
                cur = {}
    return 200, None, events


async def _make_user() -> CurrentUser:
    uid = uuid.uuid4()
    email = f"chat-{uid.hex[:8]}@example.com"
    async with AsyncSessionLocal() as s:
        s.add(User(user_id=uid, email=email, user_type="user"))
        await s.commit()
    return CurrentUser(user_id=uid, email=email, first_name="Test", user_type="user")


async def test_post_message_persists_user_message_first(client: AsyncClient):
    cid = await _new_conversation(client)
    status, _, events = await _stream(client, cid, "What is a deductible?")
    assert status == 200
    names = [e["event"] for e in events]
    assert names[0] == "user_message_persisted"
    assert names[1] == "assistant_message_started"
    got = await client.get(f"/v1/conversations/{cid}")
    assert got.json()["messages"][0]["role"] == "user"


async def test_streaming_emits_expected_event_sequence(client: AsyncClient):
    cid = await _new_conversation(client)
    _, _, events = await _stream(client, cid, "What is a copay?")
    names = [e["event"] for e in events]
    assert names[0] == "user_message_persisted"
    assert names[1] == "assistant_message_started"
    for expected in (
        "tool_call_started",
        "tool_call_completed",
        "token",
        "citation_added",
        "assistant_message_completed",
    ):
        assert expected in names, f"missing {expected}"
    assert names[-1] == "done"
    tokens = [e for e in events if e["event"] == "token"]
    assert any(e["data"].get("tier") in ("A", "B", "C") for e in tokens)


async def test_streaming_persists_assistant_message_on_completion(client: AsyncClient):
    cid = await _new_conversation(client)
    _, _, events = await _stream(client, cid, "Explain coinsurance")
    completed = next(e for e in events if e["event"] == "assistant_message_completed")
    mid = completed["data"]["message_id"]
    got = await client.get(f"/v1/conversations/{cid}")
    asst = next(m for m in got.json()["messages"] if m["message_id"] == mid)
    assert asst["status"] == "complete"
    assert asst["content"]
    assert asst["content_chunks"]
    assert asst["token_usage_output"] is not None


async def test_stop_endpoint_marks_message_as_stopped(client: AsyncClient):
    cid = await _new_conversation(client)
    async with AsyncSessionLocal() as s:
        s.add(Message(conversation_id=uuid.UUID(cid), sequence_number=1, role="assistant", status="streaming"))
        await s.commit()
    r = await client.post(f"/v1/conversations/{cid}/stop")
    assert r.status_code == 204
    got = await client.get(f"/v1/conversations/{cid}")
    statuses = [m["status"] for m in got.json()["messages"]]
    assert "stopped" in statuses and "streaming" not in statuses


async def test_per_case_mode_loads_case_context_into_agent(client: AsyncClient):
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=DEV_USER_ID, status="open")
        s.add(cf)
        await s.commit()
        await s.refresh(cf)
        case_id = str(cf.case_file_id)
    cid = await _new_conversation(client, case_id=case_id)
    _, _, events = await _stream(client, cid, "Why did insurance only cover this much?")
    tool_names = [e["data"]["tool_name"] for e in events if e["event"] == "tool_call_started"]
    assert "pg_case_file_get" in tool_names  # per-case pulls the case data


async def test_freeform_mode_omits_case_context(client: AsyncClient):
    cid = await _new_conversation(client)  # freeform
    _, _, events = await _stream(client, cid, "What is an EOB?")
    tool_names = [e["data"].get("tool_name") for e in events if e["event"] == "tool_call_started"]
    assert "pg_case_file_get" not in tool_names  # freeform never touches a case file


async def test_freeform_specific_situation_returns_create_case_cta(client: AsyncClient):
    cid = await _new_conversation(client)
    _, _, events = await _stream(
        client,
        cid,
        "I got a $4,200 bill from Hospital X and Aetna only paid $800 — is that right?",
    )
    completed = next(e for e in events if e["event"] == "assistant_message_completed")
    citations = completed["data"].get("citations") or []
    assert any(c.get("action_type") == "create_case_cta" for c in citations)


async def test_rate_limit_30_per_hour_returns_429(client: AsyncClient):
    u = await _make_user()
    app.dependency_overrides[current_user] = lambda: u
    try:
        cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
        async with AsyncSessionLocal() as s:
            for i in range(1, 31):
                s.add(Message(conversation_id=uuid.UUID(cid), sequence_number=i, role="user", content=f"m{i}", status="complete"))
            await s.commit()
        r = await client.post(f"/v1/conversations/{cid}/messages", json={"content": "one more"})
        assert r.status_code == 429
        assert r.json()["code"] == "RATE_LIMIT_REACHED"
    finally:
        app.dependency_overrides.pop(current_user, None)


async def test_cost_cap_10_per_day_returns_429(client: AsyncClient):
    u = await _make_user()
    app.dependency_overrides[current_user] = lambda: u
    try:
        cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
        async with AsyncSessionLocal() as s:
            s.add(Message(conversation_id=uuid.UUID(cid), sequence_number=1, role="assistant", content="x", status="complete", estimated_cost_usd=10.5))
            await s.commit()
        r = await client.post(f"/v1/conversations/{cid}/messages", json={"content": "another"})
        assert r.status_code == 429
        assert r.json()["code"] == "COST_CAP_REACHED"
        assert "resets_at" in r.json()
    finally:
        app.dependency_overrides.pop(current_user, None)


async def test_phi_in_title_blocks_title_generation(client: AsyncClient):
    cid = await _new_conversation(client)
    # First message: dollar amount in a billing context → PHI signal → title blocked.
    await _stream(client, cid, "My bill balance is $4,231.55 due now please")
    got = await client.get(f"/v1/conversations/{cid}")
    assert got.json()["title"] == "Untitled conversation"


async def test_knowledge_gap_logged_when_subagent_self_reports(client: AsyncClient):
    cid = await _new_conversation(client)
    await _stream(client, cid, "Are rare experimental treatments usually covered?")
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(KnowledgeGapLog))).scalars().all()
    assert any("rare" in (r.query or "").lower() for r in rows)
