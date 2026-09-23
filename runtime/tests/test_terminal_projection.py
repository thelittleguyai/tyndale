"""The terminal projection matches the terminal (e2e re-test 2026-09-23, item 2).

On the specimen's ``system_error`` the status card read "Audit ready" with all four checkmarks
ABOVE the "something on my end hiccuped" apology: the client inferred "ready" from "every bar
done", and an audit_incomplete run marked the audit bar done whatever its reason. The card's
variant and headline are now decided server-side from the terminal, one row per terminal
below — and a card written before this fix is re-projected when the thread is read.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.agents import thread_bridge
from app.agents.context_loader import orchestration_step
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.messages import Message

READY = orchestration_step("status_card.headline_ready")
FAILED = orchestration_step("status_card.headline_failed")
NEEDS_DOCS = orchestration_step("status_card.headline_needs_documents")

# status, incomplete_reason → (variant, headline, the four stage states in order)
TERMINALS = {
    ("audit_complete", None): ("ready", READY, ["done", "done", "done", "done"]),
    ("resolved", None): ("ready", READY, ["done", "done", "done", "done"]),
    ("archived", None): ("ready", READY, ["done", "done", "done", "done"]),
    ("audit_incomplete", "system_error"): ("failed", FAILED, ["done", "done", "done", "failed"]),
    ("audit_incomplete", "needs_documents"): ("needs_documents", NEEDS_DOCS, ["done", "done", "done", "waiting"]),
    ("extraction_failed", None): ("failed", None, ["failed", "pending", "pending", "pending"]),
    ("not_a_bill", None): ("failed", None, ["failed", "pending", "pending", "pending"]),
    ("attest_declined", None): ("closed", None, ["pending", "pending", "pending", "pending"]),
}


def test_every_terminal_status_has_a_decided_card():
    """A new terminal cannot slip in without a row here — and so without a decided header."""
    assert {status for status, _ in TERMINALS} == thread_bridge._TERMINAL


@pytest.mark.parametrize(("key", "want"), list(TERMINALS.items()), ids=[f"{s}:{r}" for s, r in TERMINALS])
def test_the_card_for_each_terminal(key, want):
    status, reason = key
    variant, headline, states = want
    card = thread_bridge.status_card_payload(status, incomplete_reason=reason)
    assert card["variant"] == variant
    assert card["headline"] == headline
    assert [s["state"] for s in card["stages"]] == states
    assert card["terminal"] is True
    # "ready" is said on a complete audit and NOWHERE else — the bug in one line
    assert (card["headline"] == READY) == (variant == "ready")


def test_no_checkmark_past_a_failed_stage():
    for (status, reason), _ in TERMINALS.items():
        states = [s["state"] for s in thread_bridge.status_card_payload(status, incomplete_reason=reason)["stages"]]
        if "failed" in states:
            assert "done" not in states[states.index("failed"):], (status, reason)


def test_the_live_states_keep_their_header_rules():
    working = thread_bridge.status_card_payload("in_progress")
    assert working["variant"] == "working" and working["headline"] == orchestration_step("status_card.headline_working")
    paused = thread_bridge.status_card_payload("encounter_verification_pending")
    assert paused["variant"] == "paused" and paused["headline"] is None and paused["paused"] is True


def test_the_prototypes_own_words_moved_into_the_registry_verbatim():
    assert READY == "Audit ready"
    assert orchestration_step("status_card.headline_working") == "Working on your audit"
    assert FAILED and not FAILED.startswith("<MISSING") and "ready" not in FAILED.lower()


# ── the bridge writes it, and a stale card is re-projected on read ──────────────────────
@pytest.fixture
def chat_first_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)


async def _case_thread(client: AsyncClient) -> tuple[str, str]:
    r = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    assert r.status_code == 200, r.text
    return r.json()["case_file_id"], r.json()["conversation_id"]


async def _card(conv_id: str) -> dict:
    async with AsyncSessionLocal() as s:
        m = (
            await s.execute(
                select(Message).where(
                    Message.conversation_id == uuid.UUID(conv_id), Message.kind == "status_card_update"
                )
            )
        ).scalar_one()
    return m.payload


@pytest.mark.asyncio
async def test_a_system_error_thread_is_never_told_its_audit_is_ready(client: AsyncClient, chat_first_on):
    case_id, conv_id = await _case_thread(client)
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id))
            .values(status="audit_incomplete", audit_incomplete_reason="system_error")
        )
        await s.commit()
    await thread_bridge.bridge_case_state(case_id)
    card = await _card(conv_id)
    assert card["variant"] == "failed" and card["headline"] == FAILED
    assert card["stages"][-1]["state"] == "failed"


@pytest.mark.asyncio
async def test_a_card_written_before_the_fix_is_re_projected_when_the_thread_is_read(client: AsyncClient, chat_first_on):
    case_id, conv_id = await _case_thread(client)
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id))
            .values(status="audit_incomplete", audit_incomplete_reason="system_error")
        )
        # the specimen's card: every bar done, no variant — what the old projection wrote
        stale = {
            "stages": [{"key": k, "label": k, "state": "done"} for k in ("extraction", "translate", "encounter", "audit")],
            "terminal": True, "paused": False, "marker": "status_card",
        }
        await s.execute(
            update(Message)
            .where(Message.conversation_id == uuid.UUID(conv_id), Message.kind == "status_card_update")
            .values(payload=stale)
        )
        await s.commit()

    got = (await client.get(f"/v1/conversations/{conv_id}")).json()
    card = next(m for m in got["messages"] if m["kind"] == "status_card_update")["payload"]
    assert card["variant"] == "failed" and card["headline"] == FAILED
    assert (await _card(conv_id))["variant"] == "failed"  # persisted, not just served

    # an unchanged card is not rewritten on every read
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(Message).where(
            Message.conversation_id == uuid.UUID(conv_id), Message.kind == "status_card_update"))).scalar_one()
        stamp = before.payload
    await client.get(f"/v1/conversations/{conv_id}")
    assert (await _card(conv_id)) == stamp
