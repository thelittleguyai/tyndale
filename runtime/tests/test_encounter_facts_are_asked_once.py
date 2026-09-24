"""Encounter facts are asked ONCE (e2e round 3, R1 — reproduced twice on dev).

Guided specimen dc0ed582: three charges confirmed in the intake, then — while the audit ran — the
thread screen's mount-time POST /extract re-translated the bill, APPENDED three re-worded copies
under fresh line_item_ids and wrote encounter_verification_pending over audit_running: "a second
set of the same three cards, differently worded, unanswered". Morning specimen 36736626: the same
mount-time POST on a COMPLETED case (the CAS refused four times, the translate ran anyway) flipped
audit_complete → encounter_verification_pending and projected a verification:1 card for a charge
answered hours earlier. Identity was the row a run minted, never the charge.

Now: fact_id = uuid5(case, CODE|DOS|k); answers are keyed by it; every surface builds its card
list from one registry; /extract is idempotent and claim-guarded; a finished audit re-opens only
for a new document (or the user asking) — and then asks only what changed.
"""

from __future__ import annotations

import asyncio
import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import bill_detective, encounter_facts, orchestrator
from app.agents.runner import RunResult
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.conversations import Conversation
from app.db.models.messages import Message
from app.tools.db_tools import _pg_store_line_item

BILL_TEXT = (
    "ITEMIZED STATEMENT\nMaple Grove Clinic\nDATE OF SERVICE: 09/02/2026\n"
    "99214 OFFICE VISIT EST 250.00\n36415 VENIPUNCTURE 25.00\n85025 CBC 40.00\n"
    "81002 URINALYSIS 18.00\n"
)
FIRST_BILL = [("99214", "A visit with a doctor you've seen before"), ("36415", "Blood drawn"),
              ("85025", "A blood count test")]
# the same charges, worded differently (what a second translate run actually produced)
REWORDED = [("99214", "A visit with an established doctor"), ("36415", "A blood draw"),
            ("85025", "A complete blood count")]


@pytest.fixture
def chat_first_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)


@pytest.fixture
def real_translate(monkeypatch):
    """Real mode with a translate pass that stores through the REAL tool (a fresh uuid4
    line_item_id per call, exactly as in production). ``readings`` is the bill each successive
    read sees; ``calls`` counts the reads."""
    s = get_settings()
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "litellm_proxy_url", None)
    state = {"calls": 0, "readings": [FIRST_BILL], "delay": 0.0}

    async def translate(case_file_id, mode="translate", **_):
        assert mode == "translate"
        n = state["calls"]
        state["calls"] += 1
        await asyncio.sleep(state["delay"])
        bill = state["readings"][min(n, len(state["readings"]) - 1)]
        for code, words in bill:
            await _pg_store_line_item({
                "case_file_id": case_file_id, "code": code, "raw_description": code,
                "plain_language_translation": words, "high_risk": code == "99214",
            })
        return RunResult(final_text="", tool_calls=[{}] * len(bill), usage={})

    monkeypatch.setattr(bill_detective, "run", translate)
    return state


def _fixture_mode(monkeypatch, on: bool = True):
    """The AUDIT runs on the fixture path (no real agents); reads stay on the fake translate."""
    monkeypatch.setattr(get_settings(), "use_real_claude", not on)


async def _new_case(**fields) -> str:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        cf = CaseFile(
            user_id=u.user_id,
            status=fields.pop("status", "open"),
            intake_mode=fields.pop("intake_mode", "guided"),
            intake_status=fields.pop("intake_status", "in_progress"),
            documents=fields.pop("documents", [{
                "document_id": str(uuid.uuid4()), "document_type": "itemized_bill",
                "filename": "bill.pdf", "ocr_text": BILL_TEXT, "extraction_status": "extracted",
                "ocr_text_chars": len(BILL_TEXT),
            }]),
            date_of_service=datetime.date(2026, 9, 2),
            **fields,
        )
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _case(cfid: str) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))
        ).scalar_one()


async def _cards(cfid: str) -> list[dict]:
    async with AsyncSessionLocal() as s:
        conv = (
            await s.execute(select(Conversation).where(Conversation.case_id == uuid.UUID(cfid)))
        ).scalars().first()
        if conv is None:
            return []
        rows = (
            await s.execute(
                select(Message)
                .where(Message.conversation_id == conv.conversation_id)
                .where(Message.kind == "verification_request")
                .order_by(Message.sequence_number)
            )
        ).scalars().all()
        return [dict(m.payload) for m in rows]


# ── the identity ───────────────────────────────────────────────────────────────────────────
def test_the_fact_id_is_the_charge_not_its_wording_or_its_row():
    cfid = str(uuid.uuid4())

    def run(bill):  # a translate run: fresh row ids, whatever wording the model chose
        return [{"line_item_id": str(uuid.uuid4()), "code": c, "plain_language_translation": w}
                for c, w in bill]

    first = encounter_facts.stamp(run(FIRST_BILL), cfid, "2026-09-02")
    second = encounter_facts.stamp(run(REWORDED), cfid, "2026-09-02")
    assert [f["fact_id"] for f in first] == [f["fact_id"] for f in second]
    assert {f["line_item_id"] for f in first}.isdisjoint({f["line_item_id"] for f in second})
    # the documented scheme, exactly — Brock's planner spec depends on it
    assert first[0]["fact_id"] == str(uuid.uuid5(uuid.UUID(cfid), "enc-v1|99214|2026-09-02|1"))
    # two identical charges on one day are two facts (a duplicate charge is what we audit)
    twice = encounter_facts.stamp(run([("96372", "a shot"), ("96372", "a shot")]), cfid, "2026-09-02")
    assert twice[0]["fact_id"] != twice[1]["fact_id"]
    # modifiers are part of the code, however they were typed
    assert encounter_facts.normalize_code("99214 25") == encounter_facts.normalize_code("99214-25") == "99214-25"
    # a line's own date of service wins over the case's
    own = encounter_facts.stamp([{"code": "99214", "date_of_service": "2026-09-09"}], cfid, "2026-09-02")
    assert own[0]["fact_id"] != first[0]["fact_id"]
    # a persisted id is never recomputed (a date learned later must not re-key an answered fact)
    kept = encounter_facts.stamp([{**first[0]}], cfid, "2026-10-01")
    assert kept[0]["fact_id"] == first[0]["fact_id"]


# ── the guided specimen ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_guided_answers_mean_the_audit_emits_no_new_verification_cards(
    client: AsyncClient, chat_first_on, real_translate, monkeypatch
):
    cfid = await _new_case()
    first = await orchestrator.extract_line_items(cfid)  # the intake's own background read
    assert first.status == "encounter_verification_pending" and len(first.line_items) == 3
    assert all(li.fact_id for li in first.line_items)

    # the intake's confirmations screen asks exactly the three facts, and records them
    state = (await client.get("/v1/intake/state", params={"case_file_id": cfid})).json()
    if state["current_step"] == "confirmations":
        assert {li["fact_id"] for li in state["screen"]["data"]["line_items"]} == {
            li.fact_id for li in first.line_items
        }
    r = await client.post("/v1/intake/answer", json={
        "case_file_id": cfid, "screen": "confirmations", "action": "continue",
        "values": {"confirmations": [{"line_item_id": li.line_item_id, "response": "yes"}
                                     for li in first.line_items]},
    })
    assert r.status_code == 200, r.text
    assert (await _case(cfid)).status == "encounter_verified"

    # /intake/run starts the audit … and the thread screen mounts and posts /extract mid-audit
    await orchestrator._set_status(cfid, "audit_running")
    mount = await client.post(f"/v1/audit/{cfid}/extract")
    assert mount.status_code == 200, mount.text
    assert real_translate["calls"] == 1  # never a second read
    assert (await _case(cfid)).status == "audit_running"  # never overwritten mid-audit

    _fixture_mode(monkeypatch)
    await orchestrator.finalize_audit(cfid)
    assert (await _case(cfid)).status == "audit_complete"
    await client.post(f"/v1/audit/{cfid}/extract")  # and a later visit to the thread

    cf = await _case(cfid)
    assert len(cf.line_items) == 3  # nothing appended
    cards = await _cards(cfid)
    carded = [li["line_item_id"] for card in cards for li in card["line_items"]]
    assert sorted(carded) == sorted(li.line_item_id for li in first.line_items)  # zero new cards
    for card in cards:  # and the one card shows the intake's answers, owing nothing
        assert card["awaiting"] == []
        assert set(card["answered"].values()) == {"yes"}


# ── the morning specimen ───────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_completed_case_receiving_free_text_stays_completed(
    client: AsyncClient, chat_first_on, real_translate, monkeypatch
):
    cfid = await _new_case(intake_mode="chat_first")
    first = await orchestrator.extract_line_items(cfid)
    confs = [{"line_item_id": li.line_item_id, "response": "yes"} for li in first.line_items]
    _fixture_mode(monkeypatch)
    r = await client.post(f"/v1/audit/{cfid}/confirmations", json={"confirmations": confs})
    assert r.status_code == 200, r.text
    assert (await _case(cfid)).status == "audit_complete"  # the background audit ran (fixture finalize)
    _fixture_mode(monkeypatch, on=False)

    real_translate["readings"] = [REWORDED]
    # the thread re-opened hours later: the mount-time /extract, then one free-text message
    assert (await client.post(f"/v1/audit/{cfid}/extract")).status_code == 200
    said = await client.post(f"/v1/audit/{cfid}/verify-text", json={"utterance": "the first one is right"})
    assert said.status_code == 409
    assert real_translate["calls"] == 1
    cf = await _case(cfid)
    assert cf.status == "audit_complete" and len(cf.line_items) == 3

    # the chokepoint itself refuses: chat / mapper / a re-mounted screen carry no reopen reason
    assert await orchestrator._set_status(cfid, "encounter_verification_pending") is False
    assert (await _case(cfid)).status == "audit_complete"

    # a re-sent answer set is acknowledged without restarting anything; a different one is refused
    again = await client.post(f"/v1/audit/{cfid}/confirmations", json={"confirmations": confs})
    assert again.status_code == 200 and again.json()["audit_started"] is False
    changed = [{**confs[0], "response": "no"}]
    assert (await client.post(f"/v1/audit/{cfid}/confirmations", json={"confirmations": changed})).status_code == 409
    assert (await _case(cfid)).status == "audit_complete"

    # reading the thread tells the client the card is answered and owes nothing
    conv = (await client.get("/v1/conversations", params={"case_id": cfid, "mode": "per_case", "limit": 1})).json()
    detail = (await client.get(f"/v1/conversations/{conv['conversations'][0]['conversation_id']}")).json()
    cards = [m["payload"] for m in detail["messages"] if m["kind"] == "verification_request"]
    assert cards and all(c["awaiting"] == [] and len(c["answered"]) == len(c["line_items"]) for c in cards)


@pytest.mark.asyncio
async def test_a_card_written_before_fact_ids_is_refreshed_not_re_asked(client: AsyncClient, chat_first_on):
    """The dev specimens' threads hold cards with no fact_id and no answered/awaiting — the
    refresh maps them through line_item_id."""
    items = [{"line_item_id": f"li-{i}", "code": c, "plain_language_translation": w}
             for i, (c, w) in enumerate(FIRST_BILL)]
    cfid = await _new_case(
        intake_mode="chat_first", status="audit_complete", line_items=items,
        encounter_confirmations=[{"line_item_id": "li-0", "response": "yes", "user_note": None},
                                 {"line_item_id": "li-1", "response": "not_sure", "user_note": None}],
    )
    from app.agents import thread_bridge

    async with AsyncSessionLocal() as s:
        conv = await thread_bridge.get_case_conversation(s, cfid, create_owner=(await _case(cfid)).user_id)
        await thread_bridge._insert(s, conv, "verification_request", {
            "marker": "verification:0", "group_index": 0, "intro": "i", "nudge": "n", "line_items": items,
        })
        await s.commit()
        conv_id = str(conv.conversation_id)
    detail = (await client.get(f"/v1/conversations/{conv_id}")).json()
    (card,) = [m["payload"] for m in detail["messages"] if m["kind"] == "verification_request"]
    assert card["answered"] == {"li-0": "yes", "li-1": "not_sure"}
    assert card["awaiting"] == []  # the audit is finished: nothing is owed, li-2 included


# ── a NEW document ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_rerun_after_a_new_document_re_asks_only_the_changed_facts(
    client: AsyncClient, chat_first_on, real_translate, monkeypatch
):
    cfid = await _new_case(intake_mode="chat_first")
    first = await orchestrator.extract_line_items(cfid)
    confs = [{"line_item_id": li.line_item_id, "response": "yes"} for li in first.line_items]
    _fixture_mode(monkeypatch)
    await client.post(f"/v1/audit/{cfid}/confirmations", json={"confirmations": confs})
    assert (await _case(cfid)).status == "audit_complete"
    _fixture_mode(monkeypatch, on=False)
    before = {li.fact_id: li for li in first.line_items}

    # a second bill arrives: the re-read sees the old charges re-worded plus one new charge
    real_translate["readings"] = [FIRST_BILL, [*REWORDED, ("81002", "A urine test")]]
    await orchestrator.reread_for_new_document(cfid)
    assert real_translate["calls"] == 2

    cf = await _case(cfid)
    assert cf.status == "encounter_verification_pending"  # re-opened — by a new document only
    reg = encounter_facts.registry(cf)
    assert [f["code"] for f in reg.pending] == ["81002"]  # only the changed fact is asked
    for f in reg.facts:  # the answered facts kept their row, their id and the words answered
        if f["fact_id"] in before:
            assert f["line_item_id"] == before[f["fact_id"]].line_item_id
            assert f["plain_language_translation"] == before[f["fact_id"]].plain_language_translation
    cards = await _cards(cfid)
    assert len(cards) == 2 and [li["code"] for li in cards[1]["line_items"]] == ["81002"]
    assert cards[0]["awaiting"] == [] and cards[1]["awaiting"] == [reg.pending[0]["line_item_id"]]

    # answering the one new fact merges with the three on file and runs the audit again
    _fixture_mode(monkeypatch)
    new = [{"line_item_id": reg.pending[0]["line_item_id"], "response": "yes"}]
    r = await client.post(f"/v1/audit/{cfid}/confirmations", json={"confirmations": new})
    assert r.status_code == 200 and r.json()["audit_started"] is True
    cf = await _case(cfid)
    assert len(cf.encounter_confirmations) == 4 and not encounter_facts.registry(cf).pending
    assert cf.status == "audit_complete"


@pytest.mark.asyncio
async def test_a_rerun_that_finds_nothing_new_leaves_the_case_where_it_was(
    client: AsyncClient, chat_first_on, real_translate, monkeypatch
):
    cfid = await _new_case(intake_mode="chat_first")
    first = await orchestrator.extract_line_items(cfid)
    _fixture_mode(monkeypatch)
    await client.post(f"/v1/audit/{cfid}/confirmations", json={"confirmations": [
        {"line_item_id": li.line_item_id, "response": "yes"} for li in first.line_items]})
    assert (await _case(cfid)).status == "audit_complete"
    _fixture_mode(monkeypatch, on=False)
    real_translate["readings"] = [FIRST_BILL, REWORDED]
    await orchestrator.reread_for_new_document(cfid)
    cf = await _case(cfid)
    assert cf.status == "audit_complete" and len(cf.line_items) == 3
    assert len(await _cards(cfid)) == 1


@pytest.mark.asyncio
async def test_a_new_bill_upload_is_what_triggers_the_reread(client: AsyncClient, chat_first_on, monkeypatch):
    import app.routes.upload as upload_route

    async def _bill_ocr(args):
        return {"ocr_text": BILL_TEXT, "extraction_status": "extracted"}

    monkeypatch.setattr(upload_route, "run_document_ocr", _bill_ocr)
    reread: list[tuple[str, bool]] = []

    async def fake_reread(case_file_id, *, then_audit=False):
        reread.append((case_file_id, then_audit))

    monkeypatch.setattr(upload_route, "reread_for_new_document", fake_reread)
    items = [{"line_item_id": "li-0", "code": "99214", "plain_language_translation": "A visit"}]
    cfid = await _new_case(intake_mode="chat_first", status="audit_complete", line_items=items)
    r = await client.post("/v1/upload", data={"case_file_id": cfid},
                          files=[("files", ("second-bill.pdf", b"%PDF-1.4 second", "application/pdf"))])
    assert r.status_code == 200, r.text
    uploaded_type = r.json()["uploads"][0]["document_type"]
    if uploaded_type in ("bill", "itemized_bill"):
        assert reread == [(cfid, False)]
    else:  # the classifier's call, not ours — the trigger keys off it
        assert reread == []


# ── the claim ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_two_reads_racing_never_double_the_facts(chat_first_on, real_translate):
    cfid = await _new_case(intake_mode="chat_first")
    real_translate["delay"] = 0.5
    a, b = await asyncio.gather(orchestrator.extract_line_items(cfid), orchestrator.extract_line_items(cfid))
    assert real_translate["calls"] == 1
    assert len((await _case(cfid)).line_items) == 3
    assert [li.fact_id for li in a.line_items] == [li.fact_id for li in b.line_items]


@pytest.mark.asyncio
async def test_the_chokepoint_guard():
    cases = {}
    for status in ("audit_complete", "audit_running", "encounter_verified"):
        cases[status] = await _new_case(status=status)
    reason = await _new_case(status="audit_incomplete", audit_incomplete_reason="needs_documents")

    set_status = orchestrator._set_status
    assert not await set_status(cases["audit_complete"], "encounter_verification_pending")
    assert not await set_status(cases["audit_complete"], "in_progress")
    assert not await set_status(reason, "encounter_verification_pending")
    # an audit in flight is never interrupted, whatever the reason
    assert not await set_status(cases["audit_running"], "encounter_verification_pending", reopen="new_document")
    assert not await set_status(cases["encounter_verified"], "in_progress", reopen="user_action")
    # a new document (or the user asking) may re-open a finished audit
    assert await set_status(cases["audit_complete"], "in_progress", reopen="new_document")
    assert await set_status(reason, "in_progress", reopen="user_action")
    # and forward moves are untouched
    assert await set_status(cases["audit_running"], "audit_complete")


# ── the one-off repair (migration 0060) ───────────────────────────────────────────────────
def _repair_migration():
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "app/db/migrations/versions/0060_encounter_fact_repair.py"
    spec = importlib.util.spec_from_file_location("m0060", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _li(lid: str, code: str, words: str) -> dict:
    return {"line_item_id": lid, "code": code, "plain_language_translation": words}


def test_the_repair_normalizes_codes_exactly_like_the_registry():
    mod = _repair_migration()
    for raw in ("99214", "99214 25", "99214-25", "j1100", " 01402 ", "", None):
        assert mod._code(raw) == encounter_facts.normalize_code(raw)


@pytest.mark.asyncio
async def test_the_repair_drops_the_appended_copies_and_restores_the_finished_audit():
    from app.db.models.analytics_events import AnalyticsEvent

    yes = lambda lid: {"line_item_id": lid, "response": "yes", "user_note": None}  # noqa: E731
    # the morning specimen: two answered charges, their re-worded copies appended by the
    # mount-time read, and the finished audit flipped back to verification
    morning = await _new_case(
        intake_mode="chat_first", status="encounter_verification_pending",
        line_items=[_li("a", "01402", "Anesthesia for a knee replacement"), _li("b", "64447", "A nerve block"),
                    _li("c", "01402", "Anesthesia during knee surgery"), _li("d", "64447", "A numbing shot")],
        encounter_confirmations=[yes("a"), yes("b")],
    )
    # the guided specimen: the audit's own terminal write came last, the copies stayed
    guided = await _new_case(
        status="audit_complete",
        line_items=[_li("e", "99214", "x"), _li("f", "36415", "y"), _li("g", "99214", "x2"), _li("h", "36415", "y2")],
        encounter_confirmations=[yes("e"), yes("f")],
    )
    # an unanswered charge with a code of its own is a new document's — it stays, to be asked
    newdoc = await _new_case(
        status="audit_complete",
        line_items=[_li("i", "99214", "x"), _li("j", "81002", "A urine test")],
        encounter_confirmations=[yes("i")],
    )
    async with AsyncSessionLocal() as s:
        s.add(AnalyticsEvent(event_name="audit_completed", user_id=(await _case(morning)).user_id,
                             case_file_id=uuid.UUID(morning), dedupe_key=f"audit_completed:{morning}"))
        await s.commit()

    mod = _repair_migration()
    async with AsyncSessionLocal() as s:
        await s.run_sync(lambda sync: mod.repair(sync.connection()))
        await s.commit()

    m = await _case(morning)
    assert [i["line_item_id"] for i in m.line_items] == ["a", "b"]
    assert m.status == "audit_complete" and m.audit_incomplete_reason is None
    assert [i["line_item_id"] for i in (await _case(guided)).line_items] == ["e", "f"]
    assert [i["line_item_id"] for i in (await _case(newdoc)).line_items] == ["i", "j"]
    assert [f["code"] for f in encounter_facts.registry(await _case(newdoc)).pending] == ["81002"]

    async with AsyncSessionLocal() as s:  # idempotent
        await s.run_sync(lambda sync: mod.repair(sync.connection()))
        await s.commit()
    assert [i["line_item_id"] for i in (await _case(morning)).line_items] == ["a", "b"]


# ── mid-read (the dev e2e after R1: confirmations offered on the first stored charge) ────
def test_the_planner_waits_for_the_whole_read_not_the_first_charge():
    import dataclasses

    from app.intake.planner import next_screen
    from tests.test_intake_planner import DONE

    mid_read = dataclasses.replace(DONE, line_items=1, confirmations_done=False, case_status="in_progress")
    assert next_screen(mid_read) == "reading"  # a partial list is never the facts
    read = dataclasses.replace(mid_read, case_status="encounter_verification_pending")
    assert next_screen(read) in ("facts_only", "confirmations")


@pytest.mark.asyncio
async def test_a_read_that_died_mid_way_is_read_again_from_empty(chat_first_on, real_translate):
    import datetime as _dt

    cfid = await _new_case(
        intake_mode="chat_first", status="in_progress",
        line_items=[{"line_item_id": "partial-0", "code": "99214", "plain_language_translation": "half a read"}],
        audit_heartbeat_at=_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=30),
    )
    res = await orchestrator.extract_line_items(cfid)
    assert real_translate["calls"] == 1
    cf = await _case(cfid)
    assert cf.status == "encounter_verification_pending"
    assert [li["code"] for li in cf.line_items] == ["99214", "36415", "85025"]  # the bill, once
    assert "partial-0" not in {li["line_item_id"] for li in cf.line_items}
    assert len(res.line_items) == 3


@pytest.mark.asyncio
async def test_a_live_read_is_waited_on_never_doubled(chat_first_on, real_translate, monkeypatch):
    import datetime as _dt

    monkeypatch.setattr(orchestrator, "EXTRACTION_WAIT_SECONDS", 0.2)
    cfid = await _new_case(
        intake_mode="chat_first", status="in_progress",
        line_items=[{"line_item_id": "so-far-0", "code": "99214", "code_system": "CPT",
                     "raw_description": "99214", "plain_language_translation": "first charge"}],
        audit_heartbeat_at=_dt.datetime.now(_dt.timezone.utc),
    )
    await orchestrator.extract_line_items(cfid)
    assert real_translate["calls"] == 0  # the live read owns it
    cf = await _case(cfid)
    assert cf.status == "in_progress" and len(cf.line_items) == 1


def test_the_intake_re_kicks_only_a_read_that_died():
    import datetime as _dt
    from types import SimpleNamespace

    from app.routes.intake import _kick_extraction

    class _Tasks:
        def __init__(self):
            self.added = []

        def add_task(self, fn, *a, **k):
            self.added.append(a)

    def case(beat_age_min: float | None, status: str = "in_progress"):
        beat = None if beat_age_min is None else _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=beat_age_min)
        return SimpleNamespace(case_file_id=uuid.uuid4(), status=status, audit_heartbeat_at=beat,
                               intake_state={"extraction_started_at": "2026-09-24T00:00:00+00:00"})

    live, dead = _Tasks(), _Tasks()
    _kick_extraction(case(1), live)
    _kick_extraction(case(30), dead)
    assert live.added == [] and len(dead.added) == 1
