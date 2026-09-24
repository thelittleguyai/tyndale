"""A finished case's thread is re-derived from its state on read (e2e round 3 R8).

The bridge projects on status TRANSITIONS. The M1 reveal (a5db054: a card per finding, then the
"Your game plan" link) therefore reached only cases that finished after it shipped — the morning
specimen 36736626, completed the same day, still had the numbers and "that's the complete audit"
but no finding and no way to the results page. Now reading a finished thread reconciles it: the
first read draws what is missing, and every later read writes nothing.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.agents import thread_bridge
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.db.models.messages import Message


@pytest.fixture
def chat_first_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)


async def _thread(conv_id: str) -> list[Message]:
    async with AsyncSessionLocal() as s:
        return list((await s.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(conv_id)).order_by(Message.sequence_number)
        )).scalars().all())


def _markers(msgs: list[Message]) -> list[str]:
    return [(m.payload or {}).get("marker") for m in msgs if (m.payload or {}).get("marker")]


@pytest.mark.asyncio
async def test_a_case_finished_before_the_reveal_existed_gets_it_on_the_next_read(client: AsyncClient, chat_first_on):
    up = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    case_id, conv_id = up.json()["case_file_id"], up.json()["conversation_id"]
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()
        cf.status = "audit_complete"
        cf.documents = [{"document_type": "bill", "filename": "bill.pdf"}, {"document_type": "eob", "filename": "eob.pdf"}]
        finding = Finding(
            case_file_id=uuid.UUID(case_id), finding_type="payer_side", category="cost_sharing_miscalculation",
            subagent_source="math_person", voice_tier="A",
            facts={"provider_billed": 1200.0, "eob_member_responsibility": 800.0, "tyndale_computed": 300.0, "gap": 500.0},
        )
        s.add(finding)
        await s.commit()
        finding_marker = f"finding:{finding.finding_id}"
    await thread_bridge.bridge_case_state(case_id)
    assert {finding_marker, "moment:gameplan"} <= set(_markers(await _thread(conv_id)))

    # the thread as it stood for every case finished before a5db054: no finding card, no link
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Message).where(
            Message.conversation_id == uuid.UUID(conv_id),
            Message.payload["marker"].astext.in_([finding_marker, "moment:gameplan", "findings:header"]),
        ))
        await s.commit()
    assert finding_marker not in _markers(await _thread(conv_id))

    detail = (await client.get(f"/v1/conversations/{conv_id}")).json()
    kinds = {(m["payload"] or {}).get("marker"): m for m in detail["messages"]}
    assert finding_marker in kinds and kinds[finding_marker]["payload"]["variant"] == "finding"
    assert kinds["moment:gameplan"]["payload"]["next_route"] == f"/audit/{case_id}"
    assert "findings:header" in kinds

    count = len(await _thread(conv_id))
    await client.get(f"/v1/conversations/{conv_id}")  # a second read writes nothing
    assert len(await _thread(conv_id)) == count
    assert sorted(_markers(await _thread(conv_id))) == sorted(set(_markers(await _thread(conv_id))))  # no duplicates


@pytest.mark.asyncio
async def test_a_live_thread_is_not_reconciled_on_read(client: AsyncClient, chat_first_on, monkeypatch):
    up = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    conv_id = up.json()["conversation_id"]  # status 'open' — the machine owns this thread's writes
    called = []
    real = thread_bridge._reconcile

    async def spy(*a, **k):
        called.append(1)
        return await real(*a, **k)

    monkeypatch.setattr(thread_bridge, "_reconcile", spy)
    assert (await client.get(f"/v1/conversations/{conv_id}")).status_code == 200
    assert called == []
