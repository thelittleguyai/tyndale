"""Coverage-number checklist (Brock image-3 item 2): the needs-documents card grows the
audit's highest-leverage missing inputs, computed from the case (never hardcoded), saved as
user-attested facts with provenance, and the rung-2 range tightens on the next read."""

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import thread_bridge
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources.cost_share_model import rung2_range
from app.sources.coverage_checklist import coverage_checklist_items
from tests.test_thread_bridge import _li, _messages, _set_case, _upload_new_case
from tests.test_thread_bridge import chat_first_on  # noqa: F401  (fixture)


# ── compute: the list is derived from the case, never hardcoded ─────────────────────
def _case(coverage=None, line_items=None, confirmations=None):
    return SimpleNamespace(
        coverage=coverage, line_items=line_items or [], encounter_confirmations=confirmations
    )


def test_bill_only_case_asks_for_all_four_numbers_plus_visit():
    items = coverage_checklist_items(_case())
    keys = [i["key"] for i in items]
    assert keys == [
        "deductible_amount", "deductible_met", "oop_max_amount", "oop_max_met", "visit_confirm",
    ]
    assert all(i["value"] is None and not i["not_sure"] for i in items)


def test_document_supplied_value_is_not_asked_for():
    items = coverage_checklist_items(_case(coverage={"deductible_amount": 2000.0}))
    assert "deductible_amount" not in [i["key"] for i in items]  # the SBC already said


def test_user_entered_value_renders_as_completed_item():
    cov = {
        "deductible_met": 1500.0,
        "user_input_provenance": {"deductible_met": {"source": "user-entered", "at": "t"}},
    }
    item = next(i for i in coverage_checklist_items(_case(coverage=cov)) if i["key"] == "deductible_met")
    assert item["value"] == 1500.0


def test_not_sure_is_acknowledged_not_missing():
    cov = {"user_input_provenance": {"oop_max_met": {"source": "user-entered", "not_sure": True}}}
    item = next(i for i in coverage_checklist_items(_case(coverage=cov)) if i["key"] == "oop_max_met")
    assert item["not_sure"] is True and item["value"] is None


def test_visit_candidates_pass_the_plausibility_gate():
    lis = [
        {"plain_language_translation": "MRI of the brain", "raw_description": "70551"},
        {"plain_language_translation": "Payments (since last statements)", "raw_description": "x"},
        {"plain_language_translation": "", "raw_description": "Basic metabolic panel"},
        {"plain_language_translation": "MRI of the brain", "raw_description": "dup"},
    ]
    item = next(
        i for i in coverage_checklist_items(_case(line_items=lis)) if i["key"] == "visit_confirm"
    )
    assert item["candidates"] == ["MRI of the brain", "Basic metabolic panel"]


# ── the model: stated accumulators tighten the sweep ────────────────────────────────
def test_deductible_met_collapses_the_spread():
    wide = rung2_range(1000.0, {}, anchor_kind="billed")
    told = rung2_range(
        1000.0, {"deductible_amount": 2000.0, "deductible_met": 2000.0}, anchor_kind="billed"
    )
    assert (told.high - told.low) < (wide.high - wide.low)
    assert told.high < wide.high  # the deductible-first ceiling is gone — it is met


def test_oop_remaining_caps_every_evaluation():
    rng = rung2_range(
        1000.0, {"oop_max_amount": 500.0, "oop_max_met": 400.0}, anchor_kind="billed"
    )
    assert rng.high <= 100.0 and rng.base <= 100.0


# ── the loop: save → provenance → single card re-render → tighter range ─────────────
async def _coverage_payload(conv_id):
    msgs = await _messages(conv_id)
    cards = [m for m in msgs if (m.payload or {}).get("marker") == "needs_documents"]
    assert len(cards) == 1, "ONE checklist card, updated in place"
    return cards[0].payload["needs_documents"]


@pytest.mark.asyncio
async def test_checklist_save_persists_provenance_and_rerenders_one_card(
    client: AsyncClient, chat_first_on  # noqa: F811
):
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id, status="audit_incomplete", audit_incomplete_reason="needs_documents",
        line_items=[_li("99213")],
    )
    await thread_bridge.bridge_case_state(case_id)
    payload = await _coverage_payload(conv_id)
    keys = [i["key"] for i in payload["coverage_items"]]
    assert "deductible_met" in keys and "visit_confirm" in keys

    r = await client.post(
        f"/v1/audit/{case_id}/coverage-input", json={"field": "deductible_met", "value": 1500}
    )
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert cf.coverage["deductible_met"] == 1500.0
        prov = cf.coverage["user_input_provenance"]["deductible_met"]
        assert prov["source"] == "user-entered" and prov["at"]

    payload = await _coverage_payload(conv_id)  # STILL one card — payload updated in place
    item = next(i for i in payload["coverage_items"] if i["key"] == "deductible_met")
    assert item["value"] == 1500.0

    r = await client.post(
        f"/v1/audit/{case_id}/coverage-input", json={"field": "oop_max_met", "not_sure": True}
    )
    assert r.status_code == 200
    payload = await _coverage_payload(conv_id)
    assert next(i for i in payload["coverage_items"] if i["key"] == "oop_max_met")["not_sure"]

    r = await client.post(
        f"/v1/audit/{case_id}/coverage-input", json={"field": "favorite_color", "value": 1}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_saved_numbers_tighten_the_rung2_range_on_read(
    client: AsyncClient, chat_first_on  # noqa: F811
):
    case_id, _ = await _upload_new_case(client)
    await _set_case(case_id, status="audit_complete", line_items=[_li("99213"), _li("85025")])

    r = await client.get(f"/v1/audit/{case_id}")
    assert r.status_code == 200, r.text
    a1 = r.json()["audit"]
    assert a1["computed_source"] == "engine_rung2"
    spread1 = a1["tyndale_computed_high"] - a1["tyndale_computed_low"]

    for field, value in (("deductible_amount", 2000), ("deductible_met", 2000)):
        assert (
            await client.post(
                f"/v1/audit/{case_id}/coverage-input", json={"field": field, "value": value}
            )
        ).status_code == 200

    a2 = (await client.get(f"/v1/audit/{case_id}")).json()["audit"]
    spread2 = a2["tyndale_computed_high"] - a2["tyndale_computed_low"]
    assert spread2 < spread1  # met deductible → the deductible-first ceiling is gone


# ── explainers (item 3): registry-authored, server-rendered into every checklist item ───
def test_all_explainer_keys_render_from_the_registry():
    from app.agents.context_loader import orchestration_step
    from app.agents.thread_bridge import _EXPLAINER_KEYS, RENDER_PATH_KEYS

    for key in _EXPLAINER_KEYS.values():
        assert key in RENDER_PATH_KEYS  # the staging boot gate covers them
        text = orchestration_step(key)
        assert "MISSING-script" not in text and "PLACEHOLDER" not in text, key
        assert len(text) > 40  # real copy: what it is / where to find it / an example


@pytest.mark.asyncio
async def test_card_payload_carries_explainers(client: AsyncClient, chat_first_on):  # noqa: F811
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id, status="audit_incomplete", audit_incomplete_reason="needs_documents",
        line_items=[_li("99213")],
    )
    await thread_bridge.bridge_case_state(case_id)
    payload = await _coverage_payload(conv_id)
    assert all(i.get("explainer") for i in payload["items"])
    assert all(i.get("explainer") for i in payload["coverage_items"])


# ── item 4: checklist ⇄ chat ────────────────────────────────────────────────────────
def test_coverage_number_mapper_matrix():
    from app.agents.verification_mapper import map_coverage_number

    pending = ["deductible_amount", "deductible_met", "oop_max_amount", "oop_max_met"]
    cases = [
        ("my deductible is $2,000", "deductible_amount", 2000.0),
        ("I've paid $1,500 toward my deductible so far", "deductible_met", 1500.0),
        ("out of pocket max is 8000", "oop_max_amount", 8000.0),
        ("ive already spent 3,200.50 of my out-of-pocket", "oop_max_met", 3200.5),
    ]
    for utterance, field, value in cases:
        r = map_coverage_number(utterance, pending)
        assert r and r.field == field and r.value == value, utterance
    # ambiguity degrades to None — never a half-right guess (D4b)
    assert map_coverage_number("deductible 2000 and oop 8000", pending) is None
    assert map_coverage_number("thanks so much!", pending) is None
    # a field that isn't pending is never guessed at
    assert map_coverage_number("my deductible is $2,000", ["oop_max_amount"]) is None


@pytest.mark.asyncio
async def test_free_text_run_maps_confirms_and_acks(client: AsyncClient, chat_first_on):  # noqa: F811
    """The prompt's second harness run: enter deductible-met via FREE TEXT — the mapper
    pre-selects (writing nothing), the confirming tap saves with user-entered provenance,
    and the thread acknowledges in one line."""
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id, status="audit_incomplete", audit_incomplete_reason="needs_documents",
        line_items=[_li("99213")],
    )
    await thread_bridge.bridge_case_state(case_id)

    r = await client.post(
        f"/v1/audit/{case_id}/coverage-text",
        json={"utterance": "I have paid $1,500 toward my deductible so far"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mapped"] is True and body["field"] == "deductible_met" and body["value"] == 1500.0

    # mapping wrote NOTHING (D4b: the tap is the only state change)
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert (cf.coverage or {}).get("deductible_met") is None
    msgs = await _messages(conv_id)
    assert any(m.role == "user" and "1,500" in (m.content or "") for m in msgs)  # utterance posted

    # the confirming tap
    r = await client.post(
        f"/v1/audit/{case_id}/coverage-input", json={"field": "deductible_met", "value": 1500}
    )
    assert r.status_code == 200
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert cf.coverage["deductible_met"] == 1500.0
        assert cf.coverage["user_input_provenance"]["deductible_met"]["source"] == "user-entered"

    # one-line ack in the thread, no fanfare
    msgs = await _messages(conv_id)
    acks = [m for m in msgs if "saved" in (m.content or "") and "deductible" in (m.content or "").lower()]
    assert len(acks) == 1
    payload = await _coverage_payload(conv_id)  # still ONE card, updated
    assert next(i for i in payload["coverage_items"] if i["key"] == "deductible_met")["value"] == 1500.0


@pytest.mark.asyncio
async def test_ordinary_conversation_is_not_mapped_and_not_posted(
    client: AsyncClient, chat_first_on  # noqa: F811
):
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id, status="audit_incomplete", audit_incomplete_reason="needs_documents",
        line_items=[_li("99213")],
    )
    await thread_bridge.bridge_case_state(case_id)
    before = len(await _messages(conv_id))
    r = await client.post(
        f"/v1/audit/{case_id}/coverage-text", json={"utterance": "thanks, this is helpful!"}
    )
    assert r.status_code == 200
    assert r.json()["mapped"] is False
    assert len(await _messages(conv_id)) == before  # nothing posted — ordinary chat takes it
