"""Free-text verification mapping endpoint (D4b, DL-91). THE INVARIANT: the tap is the only thing
that changes state. Free text produces a pre-selectable SUGGESTION thread entry and NEVER writes to
the confirmations endpoint — a mapped-but-unconfirmed card persists nothing. Chat ingress (crisis)
runs before the mapper. The endpoint is hidden (404) when the chat-first flag is off."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.conversations import Conversation
from app.db.models.messages import Message


@pytest.fixture
def chat_first_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)


def _li(lid, code, desc, amt):
    return {"line_item_id": lid, "code": code, "code_system": "CPT", "raw_description": desc,
            "plain_language_translation": desc, "example_scenarios": [], "high_risk": False,
            "billed_amount": amt, "units": 1}


async def _pending_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        cf.status = "encounter_verification_pending"
        cf.line_items = [
            _li("li1", "70553", "MRI brain with contrast", 1850.0),
            _li("li2", "73721", "MRI knee without contrast", 1200.0),
        ]
        await s.commit()
    return case_id


async def _case_messages(case_id: str) -> list[Message]:
    async with AsyncSessionLocal() as s:
        conv = (
            await s.execute(
                select(Conversation).where(Conversation.case_id == uuid.UUID(case_id))
            )
        ).scalars().first()
        if conv is None:
            return []
        return list(
            (
                await s.execute(
                    select(Message).where(Message.conversation_id == conv.conversation_id)
                )
            ).scalars().all()
        )


async def _case(case_id: str) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()


@pytest.mark.asyncio
async def test_endpoint_hidden_when_flag_off(client: AsyncClient):
    case_id = await _pending_case(client)
    r = await client.post(f"/v1/audit/{case_id}/verify-text", json={"utterance": "the second is wrong"})
    assert r.status_code == 404  # flag off → endpoint hidden


@pytest.mark.asyncio
async def test_mappable_creates_suggestion_but_persists_no_confirmation(client: AsyncClient, chat_first_on):
    case_id = await _pending_case(client)
    r = await client.post(
        f"/v1/audit/{case_id}/verify-text", json={"utterance": "the second one is wrong"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "mapped"

    # THE INVARIANT: nothing committed, status not advanced.
    cf = await _case(case_id)
    assert not cf.encounter_confirmations
    assert cf.status == "encounter_verification_pending"

    # A suggestion thread entry carries the mapped answer (pre-selection, not a commit).
    msgs = await _case_messages(case_id)
    sugg = next(m for m in msgs if m.kind == "verification_suggestion")
    assert sugg.payload["mappings"] == [{"line_item_id": "li2", "intended_answer": "no"}]
    assert any(m.role == "user" and m.content == "the second one is wrong" for m in msgs)


@pytest.mark.asyncio
async def test_ambiguous_utterance_posts_nudge_not_suggestion(client: AsyncClient, chat_first_on):
    case_id = await _pending_case(client)
    r = await client.post(
        f"/v1/audit/{case_id}/verify-text", json={"utterance": "that one didn't happen"}
    )
    assert r.status_code == 200 and r.json()["result"] in ("fallback", "partial_fallback")
    msgs = await _case_messages(case_id)
    assert not any(m.kind == "verification_suggestion" for m in msgs)  # never a subset pre-select
    assert (await _case(case_id)).status == "encounter_verification_pending"


@pytest.mark.asyncio
async def test_crisis_declines_before_the_mapper(client: AsyncClient, chat_first_on):
    case_id = await _pending_case(client)
    r = await client.post(
        f"/v1/audit/{case_id}/verify-text",
        json={"utterance": "the second one is wrong and I want to kill myself"},
    )
    assert r.status_code == 200 and r.json()["result"] == "crisis"
    msgs = await _case_messages(case_id)
    assert not any(m.kind == "verification_suggestion" for m in msgs)  # never reached the mapper


@pytest.mark.asyncio
async def test_no_pending_verification_is_409(client: AsyncClient, chat_first_on):
    up = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    case_id = up.json()["case_file_id"]  # status 'open', no line items → not pending
    r = await client.post(f"/v1/audit/{case_id}/verify-text", json={"utterance": "the first is right"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_the_tap_commits_exactly_the_answered_set(client: AsyncClient, chat_first_on):
    # After a suggestion, the confirming tap uses the EXISTING confirmations endpoint — THAT is what
    # changes state, and it persists exactly what's submitted.
    case_id = await _pending_case(client)
    await client.post(f"/v1/audit/{case_id}/verify-text", json={"utterance": "the second one is wrong"})
    confirm = await client.post(
        f"/v1/audit/{case_id}/confirmations",
        json={"confirmations": [
            {"line_item_id": "li1", "response": "yes", "user_note": None},
            {"line_item_id": "li2", "response": "no", "user_note": None},
        ]},
    )
    assert confirm.status_code == 200, confirm.text
    cf = await _case(case_id)
    assert {c["line_item_id"]: c["response"] for c in cf.encounter_confirmations} == {"li1": "yes", "li2": "no"}
    # the tap advanced the state past verification (→ encounter_verified, then the bg audit) — the
    # free text never did.
    assert cf.status != "encounter_verification_pending"
