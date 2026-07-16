"""Tyndale Record API + honesty helpers (D5, DL-91 §4). Recovered/avoided totals come ONLY from
CONFIRMED outcome_report events (resolved yes|partial), never from finding estimates; the estimate
(facts['gap']) is 'identified', surfaced separately; a case with no three-number shows None, never
{0,0,0}. Endpoint assertions are per-ROW (the shared dev user accumulates cases across tests, so a
global-aggregate assertion would be polluted)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.sources.record import (
    confirmed_recovered_by_case,
    identified_estimate_from_findings,
    three_number_from_findings,
)


@pytest.fixture
def record_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_record_view", True)


async def _fresh_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


async def _set(case_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        for k, v in fields.items():
            setattr(cf, k, v)
        await s.commit()


async def _user_of(case_id: str):
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile.user_id).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()


async def _finding(case_id: str, **facts) -> None:
    async with AsyncSessionLocal() as s:
        s.add(Finding(
            case_file_id=uuid.UUID(case_id), finding_type="payer_side",
            category="cost_sharing_miscalculation", subagent_source="math_person",
            voice_tier="A", facts=facts,
        ))
        await s.commit()


async def _outcome(case_id: str, user_id, resolved: str, amount: float) -> None:
    async with AsyncSessionLocal() as s:
        s.add(FeedbackEvent(
            case_file_id=uuid.UUID(case_id), user_id=user_id, response_id="r",
            feedback_type="outcome_report", improvement_consent=False,
            payload={"outcome": {"resolved": resolved, "amount_saved": amount}},
        ))
        await s.commit()


# --- pure honesty helpers ---------------------------------------------------
def test_three_number_none_never_zeros():
    class F:
        facts = {"category": "x"}  # no three numbers

    assert three_number_from_findings([F()]) is None


def test_identified_estimate_sums_gaps_positive_only():
    class F:
        def __init__(self, gap):
            self.finding_type = "payer_side"
            self.facts = {"gap": gap}

    assert identified_estimate_from_findings([F(500), F(200), F(-10)]) == 700.0


@pytest.mark.asyncio
async def test_confirmed_recovered_counts_only_genuine_and_latest(client: AsyncClient):
    a, b, c = await _fresh_case(client), await _fresh_case(client), await _fresh_case(client)
    uid = await _user_of(a)
    await _outcome(a, uid, "yes", 400.0)  # confirmed
    await _outcome(b, uid, "pending", 999.0)  # NOT a recovery
    await _outcome(c, uid, "no", 500.0)  # NOT a recovery
    ids = [uuid.UUID(a), uuid.UUID(b), uuid.UUID(c)]
    async with AsyncSessionLocal() as s:
        rec = await confirmed_recovered_by_case(s, ids)
    assert rec.get(a) == 400.0 and b not in rec and c not in rec


# --- endpoint (per-row) -----------------------------------------------------
@pytest.mark.asyncio
async def test_record_hidden_when_flag_off(client: AsyncClient):
    assert (await client.get("/v1/record")).status_code == 404


@pytest.mark.asyncio
async def test_record_rows_recovered_from_confirmed_only(client: AsyncClient, record_on):
    a = await _fresh_case(client)
    await _finding(a, provider_billed=1200, eob_member_responsibility=800, tyndale_computed=300, gap=500)
    await _set(a, status="audit_complete")
    uid = await _user_of(a)
    await _outcome(a, uid, "yes", 400.0)
    b = await _fresh_case(client)  # audit_complete, gap estimate, but NO confirmed outcome
    await _finding(b, provider_billed=600, eob_member_responsibility=400, tyndale_computed=350, gap=200)
    await _set(b, status="audit_complete")

    r = await client.get("/v1/record")
    assert r.status_code == 200, r.text
    rows = {x["case_file_id"]: x for x in r.json()["sub_cases"]}
    assert rows[a]["recovered_so_far"] == 400.0  # the CONFIRMED $400
    assert rows[b]["recovered_so_far"] == 0.0  # a big estimate but $0 recovered "so far"
    assert rows[a]["three_number"]["tyndale_computed"] == 300.0
    assert rows[a]["resume"] == "summary"  # results-bearing → sub-case summary


def test_row_provider_fallback_chain():
    """The Record row title is the provider, never the status: extracted name → '<doc-type> visit'
    → None (the client renders a neutral 'Bill review'). Never a status label."""
    from app.routes.record import _row_provider

    class _C:
        def __init__(self, eobs=None, documents=None):
            self.eobs = eobs or []
            self.documents = documents or []

    assert _row_provider(_C(eobs=[{"provider": "Maple Grove Family Medicine"}])) == "Maple Grove Family Medicine"
    assert _row_provider(_C(documents=[{"provider_name": "Beloit Health System"}])) == "Beloit Health System"
    assert _row_provider(_C(documents=[{"document_type": "itemized_bill"}])) == "Itemized bill visit"
    assert _row_provider(_C(documents=[{"document_type": "unclassified"}])) is None  # neutral rung
    assert _row_provider(_C()) is None
    banned = {"Results ready", "Needs documents", "Verify your visit", "Auditing", "In progress"}
    for c in (_C(eobs=[{"provider": "X"}]), _C(documents=[{"document_type": "eob"}]), _C()):
        assert (_row_provider(c) or "Bill review") not in banned


def test_doc_type_label_casing_no_raw_enum():
    """Acronyms keep proper casing (EOB, not 'Eob'); no raw snake_case reaches a title."""
    from app.routes.record import _doc_type_label, _row_provider

    assert _doc_type_label("eob") == "EOB"
    assert _doc_type_label("ma_eob") == "MA EOB"
    assert _doc_type_label("gfe") == "GFE"
    assert _doc_type_label("msn") == "MSN"
    assert _row_provider(_C(documents=[{"document_type": "eob"}])) == "EOB visit"  # not "Eob visit"
    for dt in ("eob", "ma_eob", "gfe", "msn", "itemized_bill", "collections_notice", "sbc"):
        title = _row_provider(_C(documents=[{"document_type": dt}]))
        assert title and "_" not in title  # never raw snake_case reaches a title


class _C:
    def __init__(self, eobs=None, documents=None):
        self.eobs = eobs or []
        self.documents = documents or []


def test_row_state_is_a_pure_function_of_status():
    from app.routes.record import _row_state

    assert _row_state("audit_complete") == "results"
    assert _row_state("resolved") == "results"
    assert _row_state("audit_incomplete") == "needs_documents"
    assert _row_state("encounter_verification_pending") == "verifying"
    assert _row_state("audit_running") == "auditing"
    assert _row_state("open") == "in_progress"


@pytest.mark.asyncio
async def test_three_number_line_only_in_results_state(client: AsyncClient, record_on):
    """The bug: a computed three-number line under a 'Verify visit' chip. The three_number is now
    gated to the results state, so the chip (state) and the line (three_number) always agree."""
    a = await _fresh_case(client)
    # A finding with all three numbers, but the case is still mid-flow (pre-results).
    await _finding(a, provider_billed=1200, eob_member_responsibility=800, tyndale_computed=300, gap=500)
    await _set(a, status="encounter_verification_pending")
    r = await client.get("/v1/record")
    row = next(x for x in r.json()["sub_cases"] if x["case_file_id"] == a)
    assert row["state"] == "verifying"
    assert row["three_number"] is None  # gated: no results line under a non-results chip


@pytest.mark.asyncio
async def test_record_row_no_three_number_is_none(client: AsyncClient, record_on):
    a = await _fresh_case(client)
    await _set(a, status="audit_incomplete", audit_incomplete_reason="needs_documents")
    r = await client.get("/v1/record")
    row = next(x for x in r.json()["sub_cases"] if x["case_file_id"] == a)
    assert row["three_number"] is None  # needs-documents state, not {0,0,0}
