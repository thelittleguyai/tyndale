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


@pytest.mark.asyncio
async def test_record_row_no_three_number_is_none(client: AsyncClient, record_on):
    a = await _fresh_case(client)
    await _set(a, status="audit_incomplete", audit_incomplete_reason="needs_documents")
    r = await client.get("/v1/record")
    row = next(x for x in r.json()["sub_cases"] if x["case_file_id"] == a)
    assert row["three_number"] is None  # needs-documents state, not {0,0,0}
