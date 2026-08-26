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
