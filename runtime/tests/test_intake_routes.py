"""Guided intake, Phase 1 — the routes (doc 40): the planner drives every response, the case
records its front door, the timeline asks its completeness question every time, resume states
the REAL link lifetime, examples render only with an asset, and help falls back to generic."""

from __future__ import annotations

import datetime
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.case_files import CaseFile

BILL_TEXT = (
    "ITEMIZED STATEMENT\nPROVIDER: Riverton Imaging\nPATIENT NAME: TYNDALE DEV\n"
    "DATE OF SERVICE: 06/14/2026\n99284 EMERGENCY DEPT VISIT 1,200.00\n73721 MRI KNEE 1,850.00\n"
)


def _doc(kind: str, **over) -> dict:
    return {"document_id": str(uuid.uuid4()), "document_type": kind, "filename": f"{kind}.pdf",
            "ocr_text": over.pop("ocr_text", ""), **over}


async def _case(**fields) -> CaseFile:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        cf = CaseFile(user_id=u.user_id, status=fields.pop("status", "open"),
                      intake_mode=fields.pop("intake_mode", "guided"),
                      intake_status=fields.pop("intake_status", "in_progress"), **fields)
        s.add(cf)
        await s.commit()
        await s.refresh(cf)
        return cf


async def _reload(cfid) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cfid))).scalar_one()


async def _answer(client: AsyncClient, cfid, screen: str, action: str = "continue", **values) -> dict:
    r = await client.post("/v1/intake/answer", json={"case_file_id": str(cfid), "screen": screen,
                                                     "action": action, "values": values})
    assert r.status_code == 200, r.text
    return r.json()


# ── start: the front door is recorded where it happens ───────────────────────────────────
@pytest.mark.asyncio
async def test_opening_the_landing_creates_nothing_and_start_stamps_the_case_guided(client: AsyncClient):
    async with AsyncSessionLocal() as s:  # finish any unfinished guided case from earlier tests
        for cf in (await s.execute(select(CaseFile).where(CaseFile.intake_mode == "guided").where(CaseFile.intake_status == "in_progress"))).scalars():
            cf.intake_status = "complete"
        await s.commit()
    landing = (await client.get("/v1/intake/state")).json()
    assert landing["case_file_id"] is None and landing["screen"]["id"] == "welcome"
    assert landing["screen"]["copy"]["trust"].startswith("Encrypted.")  # §C10 — Brock's §1.2 key, reused
    assert landing["progress"]["line"] is None  # nothing landed: no counter, never "Step 1 of N"

    started = (await client.post("/v1/intake/start")).json()
    cf = await _reload(uuid.UUID(started["case_file_id"]))
    assert cf.intake_mode == "guided" and cf.intake_status == "in_progress"
    assert started["current_step"] == "bill" == started["screen"]["id"]
    assert started["screen"]["data"]["expect"] == "itemized_bill"
    assert "example" not in started["screen"]  # no drawn bill illustration yet → no affordance at all
    assert started["screen"]["help"]["scope"] == "generic" and started["screen"]["help"]["can_email"]


# ── the planner drives the flow; every answer is one committed write ─────────────────────
@pytest.mark.asyncio
async def test_a_commercial_case_walks_to_ready_asking_only_what_is_unknown(client: AsyncClient):
    sbc = _doc("plan_summary", ocr_text="Summary of Benefits and Coverage  Coverage Period: 07/01/2025 - 06/30/2026")
    cf = await _case(
        documents=[_doc("itemized_bill", ocr_text=BILL_TEXT), _doc("eob", date_of_service="2026-03-02"),
                   _doc("eob", date_of_service="2026-06-14"), _doc("insurance_card"), sbc],
        coverage={"payer_name": "Aetna", "member_id": "W123", "deductible_amount": 2000,
                  "oop_max_amount": 6000, "coinsurance_percent": 0.2},
        provider_name="Riverton Imaging", date_of_service=datetime.date(2026, 6, 14),
        regime_detection={"verified": True, "regime": "erisa_self_funded"}, coverage_regime="erisa_self_funded",
        line_items=[{"line_item_id": "li-1", "plain_language_translation": "An emergency room visit."}],
        status="encounter_verification_pending", intake_state={"acked": ["welcome"]},
    )
    cfid = cf.case_file_id
    seen: list[str] = []
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(cfid)})).json()
    for _ in range(12):
        sid = state["current_step"]
        seen.append(sid)
        if sid == "READY":
            break
        if sid == "bill_summary":
            rows = {r["slot"]: r["value"] for r in state["screen"]["data"]["rows"]}
            assert rows["row_provider"] == "Riverton Imaging" and rows["row_date"] == "2026-06-14"
            state = await _answer(client, cfid, sid, "no")
        elif sid == "timeline":
            tl = state["screen"]["data"]
            assert tl["plan_year_start"] == "2025-07-01"  # read from the SBC — never assumed Jan 1
            assert "March" in state["screen"]["copy"]["confirm_text"] and tl["count"] == 2
            assert [g["label"] for g in tl["gaps"]][:2] == ["July", "August"]
            assert state["screen"]["copy"]["gap_consequence"].endswith("as a range.")
            state = await _answer(client, cfid, sid, "yes")
        elif sid == "other_insurance":
            state = await _answer(client, cfid, sid, "continue", choice="no")
        elif sid == "confirmations":
            assert len(state["screen"]["data"]["line_items"]) == 1  # the engine's list, exactly
            state = await _answer(client, cfid, sid, "continue",
                                  confirmations=[{"line_item_id": "li-1", "response": "yes"}])
        else:
            state = await _answer(client, cfid, sid, "ack")
    # never asked: insurer (the documents named it), plan rules (SBC on file), plan year (the SBC
    # carries it), manual deductible/OOP (the confirmed EOB stack resolves them), coverage type
    assert seen == ["bill_summary", "timeline", "other_insurance", "facts_only", "confirmations", "readiness", "READY"], seen
    cf = await _reload(cfid)
    assert cf.coverage["all_plan_year_eobs_confirmed"] is True and cf.coverage["has_secondary_coverage"] is False
    assert cf.encounter_confirmations and cf.intake_state["progress_high_water"]
    assert state["progress"]["filled"] == 7 and state["progress"]["line"] == "All 7 done"


@pytest.mark.asyncio
async def test_adding_an_eob_after_confirming_asks_the_completeness_question_again(client: AsyncClient):
    cf = await _case(documents=[_doc("eob", date_of_service="2026-02-01")], intake_state={"acked": ["welcome"], "skipped": ["bill", "card", "insurer", "plan_rules", "plan_year"]},
                     coverage={"has_secondary_coverage": False}, regime_detection={"verified": True}, coverage_regime="erisa_self_funded")
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    assert state["current_step"] == "timeline"
    assert "one EOB" in state["screen"]["copy"]["confirm_text"]  # the singular variant
    state = await _answer(client, cf.case_file_id, "timeline", "yes")
    assert state["current_step"] != "timeline"
    async with AsyncSessionLocal() as s:  # a second EOB lands (upload attaches by case id)
        row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cf.case_file_id))).scalar_one()
        row.documents = [*row.documents, _doc("eob", date_of_service="2026-04-01")]
        await s.commit()
    again = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    assert again["current_step"] == "timeline"  # locked 5d: asked EVERY time the stack changes
    assert again["screen"]["data"]["count"] == 2


@pytest.mark.asyncio
async def test_eobs_after_the_visit_are_shown_and_do_not_count(client: AsyncClient):
    cf = await _case(documents=[_doc("eob", date_of_service="2026-05-01"), _doc("eob", date_of_service="2026-08-20", network="out", member="PAT TESTER")],
                     date_of_service=datetime.date(2026, 6, 14), coverage={"plan_effective_date": "2026-01-01"},
                     intake_state={"acked": ["welcome"], "skipped": ["bill", "card", "insurer", "plan_rules"]},
                     regime_detection={"verified": True}, coverage_regime="erisa_self_funded")
    tl = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id), "screen": "timeline"})).json()["screen"]["data"]
    after = [r for r in tl["rows"] if r["after_visit"]]
    assert len(after) == 1 and tl["count"] == 1 and tl["count_after_visit"] == 1
    assert after[0]["network"] == "out" and after[0]["member"] == "PAT TESTER" and after[0]["source"] == "upload"
    assert tl["sources_offered"] == ["upload"]  # no "forward by email", no "connect" — no dead buttons
    assert [g["label"] for g in tl["gaps"]] == ["January", "February", "March", "April", "June"]


# ── non-commercial: one honest line, then chat-first ─────────────────────────────────────
@pytest.mark.asyncio
async def test_a_medicare_case_exits_with_one_line_and_an_enum_only_event(client: AsyncClient):
    cf = await _case(documents=[_doc("insurance_card")], coverage_regime="medicare_traditional",
                     regime_detection={"verified": True, "regime": "medicare_traditional", "confidence": "high"},
                     intake_state={"acked": ["welcome"]})
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    assert state["current_step"] == "handoff" and state["screen"]["kind"] == "handoff"
    assert "For Medicare, I check your bill in our chat." in state["screen"]["copy"]["body"]
    async with AsyncSessionLocal() as s:
        ev = (await s.execute(select(AnalyticsEvent).where(AnalyticsEvent.case_file_id == cf.case_file_id).where(AnalyticsEvent.event_name == "intake_handoff"))).scalars().all()
    assert [e.properties for e in ev] == [{"population": "medicare"}] and ev[0].intake_mode == "guided"


@pytest.mark.asyncio
async def test_the_plain_coverage_type_answer_routes_the_same_way(client: AsyncClient):
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT), _doc("insurance_card")],
                     coverage={"payer_name": "Acme Health", "member_id": "X1"},
                     intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob"]})
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    assert state["current_step"] == "coverage_type"
    assert [o["value"] for o in state["screen"]["data"]["options"]][0] == "job_or_bought"
    assert (await _answer(client, cf.case_file_id, "coverage_type", choice="medicaid"))["current_step"] == "handoff"
    cf2 = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT), _doc("insurance_card")],
                      coverage={"payer_name": "Acme Health", "member_id": "X1"},
                      intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob"]})
    assert (await _answer(client, cf2.case_file_id, "coverage_type", choice="job_or_bought"))["current_step"] != "handoff"
    r = await client.post("/v1/intake/answer", json={"case_file_id": str(cf2.case_file_id), "screen": "coverage_type", "values": {"choice": "martian"}})
    assert r.status_code == 422


# ── edge states are reachable and none dead-ends (§C12) ──────────────────────────────────
@pytest.mark.asyncio
async def test_a_wrong_document_and_a_summary_bill_each_get_their_existing_copy(client: AsyncClient):
    wrong = await _case(documents=[_doc("insurance_card")], coverage={"payer_name": "Aetna", "member_id": "W1"},
                        intake_state={"acked": ["welcome"]})
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(wrong.case_file_id)})).json()
    assert state["current_step"] == "bill"
    assert "an insurance card" in state["screen"]["data"]["note"]  # §5.3 wrongdoc.card, with its slot filled
    assert state["screen"]["copy"]["no_bill"]  # …and a way on: "I don't have the bill"

    summary = await _case(documents=[_doc("bill", ocr_text="STATEMENT\nPrevious balance 500.00\nBalance forward\nAmount due 900.00")],
                          intake_state={"acked": ["welcome"]})
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(summary.case_file_id)})).json()
    assert state["current_step"] == "bill_itemized" and state["screen"]["kind"] == "coach"
    assert "itemized" in state["screen"]["copy"]["body"].lower()  # §5.2 key, carrying the request script
    kept = await _answer(client, summary.case_file_id, "bill_itemized", "skip")
    assert kept["current_step"] == "bill_summary"  # coached once, then honoured


@pytest.mark.asyncio
async def test_a_name_mismatch_hosts_the_existing_attest_machinery(client: AsyncClient):
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], attest_status="required",
                     patient_name="MARGARET OTHERPERSON", intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob", "card", "insurer", "plan_rules", "plan_year", "deductible_met", "oop_met", "other_insurance"]},
                     regime_detection={"verified": True}, coverage_regime="erisa_self_funded")
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    assert state["current_step"] == "attest"  # #13 in the concept's order — and always BEFORE the confirmations
    data = state["screen"]["data"]
    assert len(data["relationships"]) == 7 and all(r["label"] for r in data["relationships"])  # attest.menu_*
    assert data["confirm"] and data["decline_ack"]  # the confirm line + the decline path, both present
    r = await client.post("/v1/intake/answer", json={"case_file_id": str(cf.case_file_id), "screen": "attest"})
    assert r.status_code == 422  # answered through POST /v1/case/{id}/attest — the audited route


@pytest.mark.asyncio
async def test_every_confirmation_the_engine_emitted_must_be_answered_and_no_others(client: AsyncClient):
    items = [{"line_item_id": f"li-{n}", "raw_description": f"LINE {n}"} for n in range(5)]
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], line_items=items, status="encounter_verification_pending")
    body = {"case_file_id": str(cf.case_file_id), "screen": "confirmations", "values": {"confirmations": [{"line_item_id": "li-0", "response": "yes"}]}}
    assert (await client.post("/v1/intake/answer", json=body)).status_code == 422  # 1 of 5
    body["values"]["confirmations"] = [{"line_item_id": f"li-{n}", "response": "not_sure"} for n in range(5)]
    assert (await client.post("/v1/intake/answer", json=body)).status_code == 200
    assert len((await _reload(cf.case_file_id)).encounter_confirmations) == 5


# ── progress never regresses (§A8) ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_reclassified_document_keeps_its_segment_and_says_why(client: AsyncClient):
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], intake_state={"acked": ["welcome"]})
    first = await _answer(client, cf.case_file_id, "bill_summary", "no")
    assert first["progress"]["filled"] == 1 and first["progress"]["line"] == "1 of 7 — nice start"
    assert first["progress"]["note"] is None
    async with AsyncSessionLocal() as s:  # the classifier changes its mind: that was a clinical note
        row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cf.case_file_id))).scalar_one()
        row.documents = [{**row.documents[0], "document_type": "clinical_record"}]
        await s.commit()
    after = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    assert after["progress"]["filled"] == 1  # it does NOT drop
    assert after["progress"]["note"].startswith("I moved one of your papers")
    assert after["current_step"] == "bill"  # …and the planner honestly asks for a bill again


# ── save and resume (§C7) ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_returning_to_intake_offers_the_unfinished_case_with_the_real_link_lifetime(client: AsyncClient):
    from app.config import get_settings

    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], intake_state={"acked": ["welcome", "bill_summary"]})
    back = (await client.get("/v1/intake/state")).json()
    assert back["case_file_id"] == str(cf.case_file_id) and back["current_step"] == "eob"
    resume = back["resume"]
    assert resume["title"] == "Pick up where you left off." and "EOB" in resume["body"]
    minutes = get_settings().magic_link_ttl_minutes
    assert f"{minutes} minutes" in resume["link_expiry"] and "90 days" not in json.dumps(back)


# ── examples + help (§A3, §A5) ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_see_an_example_renders_only_where_an_asset_exists(client: AsyncClient):
    from app.intake.examples import EXAMPLES, example_for

    assert {k for k in EXAMPLES if example_for(k)} == {"sbc", "msn"}  # the two federal samples
    assert all(EXAMPLES[k].asset is None for k in ("itemized_bill", "eob", "insurance_card", "accumulators", "summary_vs_itemized"))
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], coverage={"payer_name": "Aetna", "member_id": "W1"},
                     intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob"]},
                     regime_detection={"verified": True}, coverage_regime="erisa_self_funded")
    sbc = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()["screen"]
    assert sbc["id"] == "plan_rules"
    ex = sbc["example"]
    assert ex["asset"]["url"].startswith("https://www.cms.gov/") and 4 <= len(ex["callouts"]) <= 6
    assert ex["source_line"].startswith("This sample comes from the U.S. government.")
    eob = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id), "screen": "eob"})).json()["screen"]
    assert eob["id"] == "eob" and "example" not in eob  # asset: null → no affordance, no empty sheet


@pytest.mark.asyncio
async def test_help_me_find_it_uses_the_payer_entry_when_there_is_one_else_generic(client: AsyncClient, monkeypatch):
    from app.intake import payer_instructions as pi

    assert pi.instructions_for("Aetna", "eob")["scope"] == "generic"  # the corpus has not landed
    entry = pi.PayerEntry("aetna", "Aetna", "eob", None, ("Sign in at aetna.com.", "Open Claims."), "public help page", False)
    monkeypatch.setitem(pi.PAYER_ENTRIES, ("aetna", "eob", None), entry)
    cf = await _case(coverage={"payer_name": "Aetna"})
    got = (await client.get("/v1/intake/help", params={"document_type": "eob", "case_file_id": str(cf.case_file_id)})).json()
    assert got["scope"] == "payer" and got["steps"][0] == "Sign in at aetna.com." and got["note"] == "These steps are for Aetna."
    assert got["verified"] is False  # §A5: public help page, not a logged-in screen — said, not hidden
    other = await _case(coverage={"payer_name": "Some Regional Plan"})
    fallback = (await client.get("/v1/intake/help", params={"document_type": "eob", "case_file_id": str(other.case_file_id)})).json()
    assert fallback["scope"] == "generic" and len(fallback["steps"]) == 5
    assert (await client.get("/v1/intake/help", params={"document_type": "fax"})).status_code == 404


def test_a_bad_payer_corpus_file_is_rejected_whole_and_never_breaks_the_runtime(tmp_path, monkeypatch):
    from app.intake import payer_instructions as pi

    d = tmp_path / "reference" / "payer_instructions"
    d.mkdir(parents=True)
    (d / "01_good.json").write_text(json.dumps({"payer_name": "Cigna", "aliases": ["Cigna Healthcare"], "entries": [
        {"document_type": "eob", "steps": ["Sign in.", "Open Claims."], "source": "logged-in screen", "verified": True}]}))
    (d / "02_bad.json").write_text(json.dumps({"payer_name": "UHC", "entries": [
        {"document_type": "eob", "steps": ["ok"]}, {"document_type": "telegram", "steps": ["nope"]}]}))
    (d / "03_broken.json").write_text("{not json")
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    table = pi.load_payer_entries({})
    assert {k[0] for k in table} == {"cigna", "cigna_healthcare"}  # the alias resolves; UHC applied NOTHING


@pytest.mark.asyncio
async def test_emailing_the_steps_uses_the_one_send_path_and_never_a_synthetic_address(client: AsyncClient, monkeypatch):
    from app.notify.email import is_synthetic_email, send_product_email

    # the REAL sender refuses a synthetic address (so an e2e sweep can never mail a .test inbox)
    assert is_synthetic_email("e2e-runner+1@e2e.tyndale.test")
    assert await send_product_email("e2e-runner+1@e2e.tyndale.test", "s", "t", kind="intake_help") is False

    sent: list[dict] = []

    async def fake_send(to_email, subject, text, html=None, *, kind):
        sent.append({"to": to_email, "subject": subject, "text": text, "kind": kind})
        return True

    monkeypatch.setattr("app.notify.email.send_product_email", fake_send)
    r = await client.post("/v1/intake/help/email", json={"document_type": "sbc"})
    assert r.status_code == 200 and r.json() == {"sent": True, "message": "Sent. Check your email."}
    assert sent[0]["kind"] == "intake_help" and "1. Sign in to your insurer's website or app." in sent[0]["text"]
    assert "$" not in sent[0]["text"]  # navigation steps only — no amounts, no claim, no document content


def test_out_of_network_eobs_are_tracked_in_their_own_bucket_without_moving_the_headline():
    from app.sources.adapters.computed_from_uploaded_eobs import compute_accumulator

    year = datetime.date.today().year
    eobs = [
        {"date_of_service": f"{year}-02-01", "amount_applied_to_deductible": 300, "network": "in"},
        {"date_of_service": f"{year}-03-01", "amount_applied_to_deductible": 200, "network": "out", "member": "PAT"},
        {"date_of_service": f"{year}-04-01", "amount_applied_to_deductible": 100},
    ]
    out = compute_accumulator(eobs, {"deductible_amount": 2000}, datetime.date(year, 6, 1), True)
    assert out.data["deductible_applied"] == 600  # the headline is what it always was
    assert out.data["buckets"]["individual_in_network"]["deductible_applied"] == 600
    assert out.data["buckets"]["individual_out_of_network"]["deductible_applied"] == 200
    assert out.data["by_network"]["unknown"]["eobs"] == 1
    assert any("out-of-network EOB" in a for a in out.assumptions)  # …and it SAYS so
    none_out = compute_accumulator(eobs[:1], {"deductible_amount": 2000}, datetime.date(year, 6, 1), True)
    assert "individual_out_of_network" not in none_out.data["buckets"]


@pytest.mark.asyncio
async def test_ready_runs_the_audit_and_hands_off_to_the_existing_results(client: AsyncClient, monkeypatch):
    ran: list[str] = []

    async def fake_finalize(case_file_id):
        ran.append(case_file_id)

    monkeypatch.setattr("app.agents.orchestrator.finalize_audit", fake_finalize)
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], status="encounter_verification_pending",
                     regime_detection={"verified": True}, coverage_regime="erisa_self_funded",
                     coverage={"has_secondary_coverage": False},
                     intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob", "card", "insurer", "plan_rules", "plan_year", "deductible_met", "oop_met"]})
    early = await client.post("/v1/intake/run", json={"case_file_id": str(cf.case_file_id)})
    assert early.status_code == 409 and "readiness" in early.text  # never past the planner's own summary
    await _answer(client, cf.case_file_id, "readiness", "ack")
    r = await client.post("/v1/intake/run", json={"case_file_id": str(cf.case_file_id)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert ran == [str(cf.case_file_id)] and body["next_route"].startswith(f"/audit/{cf.case_file_id}")
    done = await _reload(cf.case_file_id)
    assert done.intake_status == "complete" and done.intake_mode == "guided"
    async with AsyncSessionLocal() as s:
        ev = (await s.execute(select(AnalyticsEvent).where(AnalyticsEvent.case_file_id == cf.case_file_id).where(AnalyticsEvent.event_name == "intake_audit_started"))).scalars().one()
    assert ev.intake_mode == "guided" and set(ev.properties) == {"unresolved"}  # a count, never a value


@pytest.mark.asyncio
async def test_the_home_resume_card_is_registry_copy(client: AsyncClient):
    """§C7 + item 3: the dashboard's "pick up where you left off" card is a GUIDED string, so
    it is registry copy served on the closed `home` surface — the app bundles none of it."""
    from app.agents.context_loader import orchestration_step

    body = (await client.get("/v1/copy/home")).json()
    assert body["resume_title"] == orchestration_step("intake.resume.title")
    assert body["resume_body"] == orchestration_step("intake.resume.home_body")
    assert body["resume_primary"] == orchestration_step("intake.resume.primary")
    assert "{" not in body["resume_body"]  # the card has no planner call to fill a variable


# ── infer first, then ask (§A4-1): a card is read the moment it lands ────────────────────
@pytest.mark.asyncio
async def test_a_readable_card_means_which_insurer_is_never_asked(client: AsyncClient):
    """The skip-when-known rule, end to end: the planner reads a NEW card once (stored OCR text,
    no second OCR call), merges only high-confidence fields, and so never shows `insurer`."""
    card = _doc("insurance_card", ocr_text="Aetna\nMember ID: W987654321\nGroup Number: 70123\nPlan: Aetna Choice POS II")
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT), card],
                     intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob"]})
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(cf.case_file_id)})).json()
    got = await _reload(cf.case_file_id)
    assert got.coverage["payer_name"].lower().startswith("aetna") and got.coverage["member_id"] == "W987654321"
    assert got.intake_state["cards_read"] == [card["document_id"]]  # read ONCE, and remembered
    assert state["current_step"] != "insurer"
    assert "card" in state["progress"]["high_water"]


@pytest.mark.asyncio
async def test_a_card_never_overwrites_what_the_user_typed_and_a_weak_read_still_asks(client: AsyncClient):
    typed = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT),
                                   _doc("insurance_card", ocr_text="Aetna\nMember ID: W987654321")],
                        coverage={"payer_name": "Cigna"}, intake_state={"acked": ["welcome"]})
    await client.get("/v1/intake/state", params={"case_file_id": str(typed.case_file_id)})
    assert (await _reload(typed.case_file_id)).coverage["payer_name"] == "Cigna"

    # "ID:" (not "Member ID:") + an unknown payer → weak matches: nothing is merged silently
    weak = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT),
                                  _doc("insurance_card", ocr_text="ACME Health Co\nID: A12345678\nGRP: 5000")],
                       intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob"]})
    state = (await client.get("/v1/intake/state", params={"case_file_id": str(weak.case_file_id)})).json()
    assert not ((await _reload(weak.case_file_id)).coverage or {}).get("payer_name")
    assert state["current_step"] == "insurer"  # the honest fallback: ask, with the fields to fill


# ── the handoff is an EXIT: it closes the guided route and chat-first takes the case ─────
MEDICARE = dict(coverage_regime="medicare_traditional",
                regime_detection={"verified": True, "regime": "medicare_traditional", "confidence": "high"})


@pytest.mark.asyncio
async def test_the_handoff_closes_the_guided_route_and_names_chat_firsts_own_entry_point(client: AsyncClient, monkeypatch):
    """Found walking the flow: the case stayed `in_progress`, so the home card and /intake kept
    inviting a Medicare user back to the screen that had just sent them away."""
    read: list[str] = []

    async def fake_extract(case_file_id):
        read.append(case_file_id)

    monkeypatch.setattr("app.agents.orchestrator.extract_line_items", fake_extract)
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], intake_state={"acked": ["welcome"]}, **MEDICARE)
    cfid = str(cf.case_file_id)

    # classic flow (chat-first audit off): the bill is read, then the verify screen — as an upload would
    r = await client.post("/v1/intake/handoff", json={"case_file_id": cfid})
    assert r.status_code == 200, r.text
    assert r.json()["next_route"] == f"/audit/{cfid}/encounter" and read == [cfid]
    done = await _reload(cf.case_file_id)
    assert done.intake_status == "complete" and done.intake_state["handed_off"] == "medicare"
    assert done.intake_mode == "guided"  # the door it was OPENED through — a fact, not a state

    # nothing invites the user back: not the landing, not the home card, not the Open Cases card
    landing = (await client.get("/v1/intake/state")).json()
    assert landing.get("resume") is None or landing["resume"]["case_file_id"] != cfid
    dash = (await client.get("/v1/dashboard")).json()
    assert dash["guided_resume_case_id"] != cfid
    assert all(c["resume"] != "intake" for c in dash["active_cases"] if c["case_file_id"] == cfid)

    # chat-first audit on: the case gets the SAME thread an upload gets. Idempotent.
    async def fake_bootstrap(case_file_id):
        return "conv-1"

    monkeypatch.setattr("app.agents.thread_bridge.bootstrap_thread", fake_bootstrap)
    again = await client.post("/v1/intake/handoff", json={"case_file_id": cfid})
    assert again.status_code == 200 and again.json()["next_route"] == f"/audit/{cfid}/thread"
    assert again.json()["conversation_id"] == "conv-1"


@pytest.mark.asyncio
async def test_a_handoff_before_any_document_goes_to_upload_and_comes_back_through_the_same_route(client: AsyncClient):
    """No document yet → the upload screen. NOT the results screen afterwards (it would wait
    forever on a never-audited case): `handoff=1` makes the upload screen ask this route again."""
    cf = await _case(documents=[], intake_state={"acked": ["welcome"], "skipped": ["bill", "eob", "card", "insurer"],
                                                 "answers": {"coverage_type": "medicaid"}})
    r = await client.post("/v1/intake/handoff", json={"case_file_id": str(cf.case_file_id)})
    assert r.status_code == 200, r.text
    assert r.json()["next_route"] == f"/upload?caseId={cf.case_file_id}&handoff=1"
    assert (await _reload(cf.case_file_id)).intake_state["handed_off"] == "medicaid"


@pytest.mark.asyncio
async def test_a_commercial_case_cannot_be_handed_off(client: AsyncClient):
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], intake_state={"acked": ["welcome"]},
                     coverage_regime="erisa_self_funded", regime_detection={"verified": True})
    r = await client.post("/v1/intake/handoff", json={"case_file_id": str(cf.case_file_id)})
    assert r.status_code == 409 and "not a handoff" in r.text
    assert (await _reload(cf.case_file_id)).intake_status == "in_progress"


@pytest.mark.asyncio
async def test_an_unfinished_guided_case_resumes_on_the_guided_route_everywhere(client: AsyncClient, monkeypatch):
    """The Open Cases card and the Record rows sent a pre-audit case to the verify screen / its
    thread — screens that expect an intake this user has not finished. One shared test
    (`in_guided_intake`) now routes all three surfaces to /intake, with a registry label."""
    from app.agents.context_loader import orchestration_step
    from app.config import get_settings

    other = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], intake_mode="chat_first", intake_status="not_started")
    cf = await _case(documents=[_doc("itemized_bill", ocr_text=BILL_TEXT)], intake_state={"acked": ["welcome"]})
    cfid = str(cf.case_file_id)
    dash = (await client.get("/v1/dashboard")).json()  # ONE call: it is slow on a long-lived local DB
    row = next(c for c in dash["active_cases"] if c["case_file_id"] == cfid)
    assert row["resume"] == "intake" and row["label"] == orchestration_step("intake.resume.case_label")
    assert dash["guided_resume_case_id"] == cfid
    # a chat-first case in the same pre-audit status is untouched
    assert next(c for c in dash["active_cases"] if c["case_file_id"] == str(other.case_file_id))["resume"] == "encounter"

    monkeypatch.setattr(get_settings(), "enable_record_view", True)
    rec = (await client.get("/v1/record")).json()
    sub = next(c for c in rec["sub_cases"] if c["case_file_id"] == cfid)
    assert sub["resume"] == "intake" and sub["label"] == orchestration_step("intake.resume.case_label")

