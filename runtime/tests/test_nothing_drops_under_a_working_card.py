"""The drop line never renders under a working card (e2e re-test 2026-09-23, item 4).

The re-test saw "I don't have what I need to say that part yet. So I left it out. I don't
guess." under the spinning card while it read "Reading your bill". It was not a data-quality
message: it was the ACKNOWLEDGMENT. §1.4 ("Got your documents — {doc_list} from {payer}.
Reading them now…") is written at upload, the payer is only known after extraction, and a
string with a missing input renders the drop line. Now the acknowledgment picks the variant
whose inputs are known, any allowed-while-working string that still degrades is QUEUED until
the run pauses or ends, and the harness watches the thread during extraction too.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.agents import thread_bridge
from app.agents.context_loader import DEGRADATION_KEY, orchestration_step
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.messages import Message

DROP = orchestration_step(DEGRADATION_KEY)


@pytest.fixture
def chat_first_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)


async def _thread(conv_id: str) -> list[Message]:
    async with AsyncSessionLocal() as s:
        return list(
            (await s.execute(select(Message).where(Message.conversation_id == uuid.UUID(conv_id)).order_by(Message.sequence_number))).scalars()
        )


async def _ack(conv_id: str) -> Message | None:
    return next((m for m in await _thread(conv_id) if (m.payload or {}).get("marker") == "ack"), None)


def _case(**kw):
    from types import SimpleNamespace

    base = {"documents": [], "coverage": None, "eobs": None, "provider_name": None}
    return SimpleNamespace(**{**base, **kw})


def test_the_acknowledgment_says_only_what_is_known_when_it_renders():
    bill, eob = {"document_type": "bill"}, {"document_type": "eob"}
    # payer-issued papers and the payer known → his §1.4, verbatim ("from" names who issued them)
    full = thread_bridge._acknowledgment(_case(documents=[eob], coverage={"payer": "Blue Shield"}))
    assert full == orchestration_step("acknowledgment", doc_list="EOB", payer="Blue Shield")
    assert "Blue Shield" in full
    # one bill from a known provider → his single-document variant
    single = thread_bridge._acknowledgment(_case(documents=[bill], provider_name="Mercy General Hospital"))
    assert single == orchestration_step("acknowledgment_single_doc", provider="Mercy General Hospital")
    # the chat-first upload: types known, payer not yet → no payer clause, never the drop line
    no_payer = thread_bridge._acknowledgment(_case(documents=[bill, eob]))
    assert no_payer == orchestration_step("acknowledgment_no_payer", doc_list="bill and EOB")
    assert "bill and EOB" in no_payer
    # nothing classified → just "reading"
    reading = thread_bridge._acknowledgment(_case(documents=[{"filename": "x.pdf"}]))
    assert reading == orchestration_step("acknowledgment_reading")
    for text in (full, single, no_payer, reading):
        assert text.strip() != DROP.strip() and not text.startswith("<MISSING")


def test_the_insurer_is_never_named_as_the_sender_of_a_bill():
    """e2e round 3 R6 (guided specimen): one bill, the insurer typed in the intake → "Got your
    documents — bill from Blue Shield". The clause names whoever issued EVERY document — or no one."""
    bill, eob = {"document_type": "bill"}, {"document_type": "eob"}
    blue = {"payer": "Blue Shield"}
    guided = thread_bridge._acknowledgment(_case(documents=[bill], coverage=blue, provider_name="Maple Grove Clinic"))
    assert guided == orchestration_step("acknowledgment_single_doc", provider="Maple Grove Clinic")
    assert "Blue Shield" not in guided and "Maple Grove Clinic" in guided
    unknown = thread_bridge._acknowledgment(_case(documents=[bill], coverage=blue, provider_name="Amount Due"))
    assert "Blue Shield" not in unknown and " from " not in unknown  # implausible provider → no clause
    mixed = thread_bridge._acknowledgment(_case(documents=[bill, eob], coverage=blue, provider_name="Maple Grove Clinic"))
    assert mixed == orchestration_step("acknowledgment_no_payer", doc_list="bill and EOB")


@pytest.mark.asyncio
async def test_the_upload_acknowledgment_is_never_the_drop_line(client: AsyncClient, chat_first_on):
    up = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    conv_id = up.json()["conversation_id"]
    ack = await _ack(conv_id)
    assert ack is not None and ack.content.strip() != DROP.strip()
    assert "Reading" in ack.content


@pytest.mark.asyncio
async def test_a_string_that_degrades_while_the_machine_works_is_queued_until_it_pauses(
    client: AsyncClient, chat_first_on, monkeypatch
):
    up = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    case_id, conv_id = up.json()["case_file_id"], up.json()["conversation_id"]
    async with AsyncSessionLocal() as s:  # a fresh thread for the case, the ack not yet written
        await s.execute(update(Message).where(
            Message.conversation_id == uuid.UUID(conv_id), Message.kind == "system_message").values(payload={"marker": "x-removed"}))
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(status="in_progress"))
        await s.commit()
    monkeypatch.setattr(thread_bridge, "_acknowledgment", lambda _case: DROP)  # a string that degraded

    await thread_bridge.bridge_case_state(case_id)
    assert await _ack(conv_id) is None  # queued: not under the spinning card

    async with AsyncSessionLocal() as s:
        await s.execute(update(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)).values(status="encounter_verification_pending"))
        await s.commit()
    await thread_bridge.bridge_case_state(case_id)
    released = await _ack(conv_id)
    assert released is not None and released.content == DROP  # released at the first pause


# ── the harness now looks during extraction too ─────────────────────────────────────────
def _harness():
    import importlib.util
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve().parents[1] / "scripts/e2e_scenarios"
    sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location("run_scenarios", here / "run_scenarios.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_harness_knows_the_registrys_drop_line_and_flags_it_even_on_an_allowed_entry():
    mod = _harness()
    assert mod.DEGRADED_LINE == DROP.strip()
    ack = {"kind": "system_message", "payload": {"marker": "ack"}, "content": DROP}
    assert mod._renderable_while_working([ack]) == ["system_message:'ack' is the drop line"]
    fine = {"kind": "system_message", "payload": {"marker": "ack"}, "content": "Got your documents. Reading them now…"}
    assert mod._renderable_while_working([fine]) == []


def test_the_harness_watches_the_thread_while_extraction_runs():
    mod = _harness()
    case_id = "case-" + uuid.uuid4().hex[:8]
    looks = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/status"):
            looks["n"] += 1
            return httpx.Response(200, json={"status": "in_progress"})
        if path == "/v1/conversations":
            return httpx.Response(200, json={"conversations": [{"conversation_id": "c1"}]})
        if path == "/v1/conversations/c1":
            return httpx.Response(200, json={"messages": [
                {"message_id": "m1", "kind": "status_card_update", "payload": {}, "content": None},
                {"message_id": "m2", "kind": "system_message", "payload": {"marker": "ack"}, "content": DROP},
            ]})
        return httpx.Response(404)

    transport = httpx.MockTransport(_handler)
    real_client = httpx.Client

    class _Mocked(real_client):
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    mod.httpx.Client = _Mocked
    try:
        with _Mocked() as c, mod._watch_extraction(c, "http://t", case_id, every_s=0.05):
            import time

            time.sleep(0.3)  # the synchronous extraction GET, as far as the watcher knows
    finally:
        mod.httpx.Client = real_client
    assert looks["n"] >= 2  # it looked right after upload AND while the extraction ran
    fails = mod._working_phase_checks(case_id)
    assert fails and "is the drop line" in fails[0]
