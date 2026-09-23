"""The guard convicts on BASIS codes only (e2e 2026-09-23 B2).

The specimen: anesthesia 01402 billed for a knee arthroscopy, where 01382 was the correct
code. The engine found it; the prose-grounding guard DELETED the finding because 01382 — the
correct code, a REFERENCE — is not in the OCR text, then regenerated the summary without it
and the user saw "$0 … nothing hidden" while the deadline banner still cited the mismatch.

Findings now carry two code sets — `basis_codes` (grounded, convicting) and `reference_codes`
(the argument: correct code, panel, comparison — never grounded, never convicting) — stated by
the agent or derived from the category family. The guard checks only the basis; the summary
pass vouches the references; a guard drop is told to the user in doctrine voice, not as a
photo problem; the deadline's dispute basis follows the SURVIVING findings; and the review
queue's `canary` means a planted marker again, with `guard_drop` its own flag.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.sources import prose_grounding as pg

BILL = (
    "COTTONWOOD SURGERY CENTER — STATEMENT\nAccount: TST-0777\nDate of Service: 02/19/2026\n"
    "CPT 29881 Knee arthroscopy w/ meniscectomy $6,400.00\nCPT 01402 Anesthesia, knee arthroscopy $1,200.00\n"
    "TOTAL BILLED: $7,600.00"
).upper()


# ── the specimen shape survives, in every way an agent might have written it ────────────
@pytest.mark.parametrize(
    "facts, legal, rec",
    [
        # structured, with a reference-marked key (the August rule already covered this one)
        ({"billed_code": "01402", "correct_code": "01382", "line_item_id": "li-2"}, None, None),
        # structured, with a NEUTRAL key for the correct code — the specimen's likely shape
        ({"billed_code": "01402", "arthroscopy_anesthesia_code": "01382", "line_item_id": "li-2"}, None, None),
        # prose only: the correct code named inline in a description (never strippable)
        ({"code": "01402", "description": "CPT 01402 (arthroplasty anesthesia) billed; the arthroscopy takes CPT 01382."}, None, None),
        # the argument carried in the legal claim / recommendation only
        ({"code": "01402"}, {"claim": "Anesthesia must be billed under the code matching the surgery: CPT 01382."}, {"action": "ask for a corrected claim under code 01382"}),
    ],
)
def test_the_upcoding_specimen_keeps_its_reference_code(facts, legal, rec):
    verdict = pg.ground_finding(facts, legal, rec, BILL, category="upcoding — anesthesia code mismatch")
    assert verdict.action == "keep", verdict
    basis, reference = pg.code_sets(facts, legal, rec, BILL, category="upcoding — anesthesia code mismatch")
    assert basis == {"01402"} and "01382" in reference


def test_explicit_code_sets_from_the_agent_win_outright():
    facts = {"basis_codes": ["01402"], "reference_codes": ["01382", "01400"], "some_code": "01382"}
    basis, reference = pg.code_sets(facts, None, None, BILL, category="whatever")
    assert basis == {"01402"} and reference == {"01382", "01400"}
    assert pg.ground_finding(facts, None, None, BILL, category="whatever").action == "keep"
    # a stated basis code that no document contains still drops — the guard did not go soft
    bad = {"basis_codes": ["02417"], "reference_codes": ["01382"]}
    v = pg.ground_finding(bad, None, None, BILL, category="upcoding")
    assert v.action == "drop" and v.dropped_codes == ["02417"]


def test_a_basis_code_absent_from_every_document_still_drops_even_in_the_upcoding_family():
    # "billed 02417" — the canary — is a claim about the documents; nothing on the bill grounds it
    v = pg.ground_finding({"billed_code": "02417", "correct_code": "01382"}, None, None, BILL, category="upcoding")
    assert v.action == "drop" and v.dropped_codes == ["02417"]
    # and a finding with NO grounded basis cannot launder a canary through prose
    v = pg.ground_finding({"note": "the bill carried CPT 02417 twice"}, None, None, BILL, category="upcoding")
    assert v.action == "drop"


def test_the_family_rules_migrate_existing_finding_types():
    assert pg.category_family("upcoding — anesthesia code mismatch") == "upcoding"
    assert pg.category_family("E/M level not supported") == "upcoding"
    assert pg.category_family("unbundled panel components") == "unbundling"
    assert pg.category_family("duplicate line item") == "duplicate"
    assert pg.category_family("cost_sharing_audit") is None
    # unbundling: the panel is the argument
    basis, reference = pg.code_sets(
        {"component_codes": ["73721", "99213"], "note": "belong to panel CPT 80053"}, None, None, BILL.replace("01402", "73721").replace("29881", "99213"), category="unbundled panel",
    )
    assert "80053" in reference and basis == {"73721", "99213"}
    # duplicates: basis only — every code the finding names must be on the documents
    basis, reference = pg.code_sets({"code": "29881", "also_code": "01382"}, None, None, BILL, category="duplicate charge")
    assert reference == set() and {"29881", "01382"} <= basis
    assert pg.ground_finding({"code": "29881", "also_code": "01382"}, None, None, BILL, category="duplicate charge").action == "drop"


def test_the_summary_pass_vouches_a_kept_findings_reference_codes():
    """The regen path uses the SAME distinction: the LP summary may name the correct code."""
    _, refs = pg.code_sets({"billed_code": "01402", "arthroscopy_code": "01382"}, None, None, BILL, category="upcoding")
    summary = "The anesthesia line was billed as CPT 01402; the arthroscopy calls for CPT 01382."
    assert pg.summary_ungrounded_codes(summary, BILL, refs) == []
    assert pg.summary_ungrounded_codes(summary, BILL) == ["01382"]  # unvouched: still flags
    assert pg.summary_ungrounded_codes("… and CPT 02417 …", BILL, refs) == ["02417"]  # a canary never rides along


# ── the whole path: drop → notice → deadline basis → queue flags ───────────────────────
def _tripwire(which: str, codes: list[str]) -> dict:
    return {"kind": "tripwire", "which": which, "codes": codes, "category": "x", "at": "2026-09-23T00:00:00+00:00"}


def test_canary_marker_hits_and_guard_drops_are_different_things():
    from app.agents.orchestrator import canary_marker_entries, guard_drop_entries

    legit = SimpleNamespace(research_log=[_tripwire("grounding_drop", ["01382"])])
    marker = SimpleNamespace(research_log=[_tripwire("translate_drop", ["02417"])])
    scrub = SimpleNamespace(research_log=[_tripwire("grounding_scrub", [])])
    assert guard_drop_entries(legit) and not canary_marker_entries(legit)
    assert guard_drop_entries(marker) and canary_marker_entries(marker)
    assert not guard_drop_entries(scrub) and not canary_marker_entries(scrub)  # a scrub is neither


def test_the_queue_triggers_and_flags_follow_the_split():
    from app.review import queue as rq

    on = SimpleNamespace(review_trigger_first_case=False, review_trigger_low_confidence=False,
                         review_trigger_system_error=False, review_trigger_canary=True,
                         review_trigger_guard_drop=True, review_trigger_material_disagreement=False)
    base = dict(terminal_status="audit_complete", incomplete_reason=None, confidence_band="high", first_case=False,
                system_error=False, material_disagreement=False, findings_count=1, net_finding_usd=1.0, documents_fingerprint="d")
    d = rq.decide(rq.EnqueueFacts(**base, canary_flag=False, guard_drop=True), sample_pct=0, settings=on, roll=0.9)
    assert d.enqueue and d.triggers == ("guard_drop",)
    d = rq.decide(rq.EnqueueFacts(**base, canary_flag=True, guard_drop=True), sample_pct=0, settings=on, roll=0.9)
    assert d.triggers == ("canary", "guard_drop")
    off = SimpleNamespace(**{**vars(on), "review_trigger_guard_drop": False})
    assert not rq.decide(rq.EnqueueFacts(**base, canary_flag=False, guard_drop=True), sample_pct=0, settings=off, roll=0.9).enqueue


@pytest.mark.asyncio
async def test_a_drop_re_derives_the_deadlines_basis_from_survivors_and_the_thread_says_so(client: AsyncClient):
    from sqlalchemy import delete, select

    from app.agents.orchestrator import _ground_prose, guard_drop_entries
    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile
    from app.db.models.deadlines import Deadline
    from app.db.models.findings import Finding

    up = await client.post("/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")})
    case_id = up.json()["case_file_id"]
    cid = uuid.UUID(case_id)
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
        cf.documents = [{"document_id": "d1", "document_type": "bill", "extraction_status": "extracted", "ocr_text": BILL}]
        s.add(Finding(case_file_id=cid, finding_type="provider_side", category="upcoding — anesthesia code mismatch",
                      subagent_source="bill_detective", voice_tier="A",
                      facts={"billed_code": "01402", "anesthesia_code_for_arthroscopy": "01382", "line_item_id": "li-2"}))
        s.add(Finding(case_file_id=cid, finding_type="provider_side", category="phantom charge",
                      subagent_source="bill_detective", voice_tier="A", facts={"code": "02417", "gap": 300.0}))  # fabricated → drops
        s.add(Finding(case_file_id=cid, finding_type="payer_side", category="cost_sharing_audit",
                      subagent_source="math_person", voice_tier="A", facts={"line_item_id": "li-1"}))
        s.add(Deadline(case_file_id=cid, deadline_type="dispute", deadline_date=__import__("datetime").date(2026, 12, 1),
                       description="Dispute the phantom CPT 02417 charge and the anesthesia code mismatch"))
        await s.commit()

    class _Budget:
        def take_regen(self):
            return False

        def expired(self):
            return False

    try:
        composed = await _ground_prose(case_id, "Summary: CPT 01402 was billed where CPT 01382 applies.", _Budget(), "", "")
        assert composed.startswith("Summary")  # the reference code is vouched — no regen, no degrade
        async with AsyncSessionLocal() as s:
            cats = sorted(f.category for f in (await s.execute(select(Finding).where(Finding.case_file_id == cid))).scalars())
            dl = (await s.execute(select(Deadline).where(Deadline.case_file_id == cid))).scalar_one()
            cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
        assert cats == ["cost_sharing_audit", "upcoding — anesthesia code mismatch"]  # the specimen SURVIVES; the canary drops
        # the deadline no longer cites the dropped finding; its basis is the survivors
        assert "02417" not in dl.description and dl.description.startswith("Dispute basis:")
        assert "code mismatch" in dl.description.lower() or "upcoding" in dl.description.lower()
        # the case records a guard drop (not a canary in its old, conflated sense: 02417 IS a marker here)
        drops = guard_drop_entries(cf)
        assert [e["codes"] for e in drops] == [["02417"]]
        # the user-facing notice is doctrine voice, not the blurry line — and the loader's
        # missing-variable fallback is no longer the blurry line either
        from app.agents.context_loader import DEGRADATION_KEY, orchestration_step

        notice = orchestration_step("grounding.dropped_notice")
        assert "left it out" in notice and "blurry" not in notice and "photo" not in notice
        assert DEGRADATION_KEY == "degraded.missing_input"
        assert "blurry" not in orchestration_step("deadline_watch_nudge")  # a missing variable → neutral, never a photo claim
        assert "blurry" in orchestration_step("dataquality_partial_illegible", line_desc="eob.pdf")  # §5.1 only on a real partial read
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == cid))
            await s.execute(delete(Deadline).where(Deadline.case_file_id == cid))
            row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()


@pytest.mark.asyncio
async def test_pg_upsert_finding_stores_the_two_code_sets_and_the_queue_exposes_guard_drop(client: AsyncClient):
    from sqlalchemy import delete, select

    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile
    from app.db.models.findings import Finding
    from app.tools import call_tool

    up = await client.post("/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")})
    case_id = up.json()["case_file_id"]
    cid = uuid.UUID(case_id)
    try:
        out = await call_tool("pg_upsert_finding", {
            "case_file_id": case_id, "finding_type": "provider_side", "category": "upcoding",
            "facts": {"billed_code": "01402"}, "basis_codes": ["01402", "01402-QS"], "reference_codes": ["01382", "01402", "not a code"],
        })
        assert out["stored"]
        async with AsyncSessionLocal() as s:
            f = (await s.execute(select(Finding).where(Finding.case_file_id == cid))).scalar_one()
        assert f.facts["basis_codes"] == ["01402"] and f.facts["reference_codes"] == ["01382"]  # normalized, disjoint
        # the queue API filters and flags both classes
        r = await client.get("/v1/admin/review/queue", params={"guard_drop": "true", "limit": 1})
        assert r.status_code == 200 and all(i["flags"]["guard_drop"] for i in r.json()["items"])
        cfg = (await client.get("/v1/admin/review/settings")).json()
        assert {"canary", "guard_drop"} <= set(cfg["triggers"])
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == cid))
            row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()
