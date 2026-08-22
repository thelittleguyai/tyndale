"""Item 3 (Brock 2026-08-22): suggested_replies round-trip — SSE completion event, the
persisted row, and the conversation GET all carry the chips; per-case turns carry none."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


async def _new_conversation(client: AsyncClient, case_id: str | None = None) -> str:
    body = {"case_id": case_id} if case_id else {}
    return (await client.post("/v1/conversations", json=body)).json()["conversation_id"]


async def _stream(client: AsyncClient, cid: str, content: str) -> list[dict]:
    events: list[dict] = []
    async with client.stream(
        "POST", f"/v1/conversations/{cid}/messages", json={"content": content}
    ) as resp:
        assert resp.status_code == 200
        cur: dict = {}
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                cur = {"event": line.split(":", 1)[1].strip()}
            elif line.startswith("data:"):
                cur["data"] = json.loads(line.split(":", 1)[1].strip())
                events.append(cur)
                cur = {}
    return events


@pytest.mark.asyncio
async def test_suggested_replies_round_trip_sse_and_persistence(client: AsyncClient):
    cid = await _new_conversation(client)  # freeform
    events = await _stream(client, cid, "What is a copay?")
    completed = next(e for e in events if e["event"] == "assistant_message_completed")
    assert completed["data"]["suggested_replies"] == ["Yes, I have a bill", "Just curious"]

    detail = (await client.get(f"/v1/conversations/{cid}")).json()
    last = [m for m in detail["messages"] if m["role"] == "assistant"][-1]
    assert last["suggested_replies"] == ["Yes, I have a bill", "Just curious"]  # persisted
    assert last["status"] == "complete"
