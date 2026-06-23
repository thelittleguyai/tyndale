"""CO-12C.2 — benefits-doc name recognition + guided flows + completeness signal.

Proves: every benefits-doc alias classifies as the benefits doc; the summary-bill
heuristic flags a summary (and passes an itemized bill); the guided-answers route
persists its fields into coverage; and the all-plan-year-EOBs completeness signal
CO-12C sets is read by CO-12B's accumulator end-to-end.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.dev_user import DEV_USER_ID
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.ingestion.bill_heuristics import detect_summary_bill
from app.routes.upload import BENEFITS_DOC_ALIASES, _classify
from app.sources.adapters.computed_from_uploaded_eobs import (
    completeness_signal,
    compute_accumulator,
)


# --- benefits-doc name recognition -----------------------------------------
def test_benefits_doc_aliases_classify_as_plan_summary():
    for alias in BENEFITS_DOC_ALIASES:
        dtype, _ = _classify(alias)
        assert dtype == "plan_summary", f"{alias!r} -> {dtype}"
    for text in ("Evidence of Coverage", "Schedule of Benefits", "your plan (SPD) booklet"):
        assert _classify(text)[0] == "plan_summary"


# --- summary-bill heuristic (non-blocking) ----------------------------------
def test_summary_bill_flagged_with_itemized_request_script():
    text = "Mercy Hospital\nPrevious Balance $0\nBalance Forward $1,200\nAmount Due $1,200"
    res = detect_summary_bill(text)
    assert res["is_summary"] is True
    assert res["itemized_request_script"]
    assert any("balance forward" in r.lower() for r in res["reasons"])


def test_itemized_bill_not_flagged():
    text = "Mercy Hospital\n70553 MRI brain $1,200\n80053 Metabolic panel $145.50\nTotal $1,345.50"
    res = detect_summary_bill(text)
    assert res["is_summary"] is False
    assert res["itemized_request_script"] is None


# --- completeness signal: CO-12C sets the key, CO-12B reads it --------------
def test_completeness_signal_reads_co12c_key():
    assert completeness_signal(None, {"all_plan_year_eobs_confirmed": True}) is True
    assert completeness_signal(None, {"all_plan_year_eobs_confirmed": False}) is False
    assert completeness_signal(None, {}) is None


def test_completeness_end_to_end_confidence():
    eobs = [{"adjudication_date": "2026-02-01", "amount_applied_to_deductible": 200.0}]
    as_of = date(2026, 6, 1)
    confirmed = compute_accumulator(
        eobs, {}, as_of, completeness_signal(None, {"all_plan_year_eobs_confirmed": True})
    )
    unconfirmed = compute_accumulator(
        eobs, {}, as_of, completeness_signal(None, {"all_plan_year_eobs_confirmed": False})
    )
    assert unconfirmed.confidence < confirmed.confidence
    assert any("history may be incomplete" in a for a in unconfirmed.assumptions)
    assert not any("history may be incomplete" in a for a in confirmed.assumptions)


# --- guided-answers route persists into coverage ----------------------------
@pytest.mark.asyncio
async def test_guided_answers_persist_into_coverage(client: AsyncClient):
    async with AsyncSessionLocal() as s:
        case = CaseFile(user_id=DEV_USER_ID, status="open")
        s.add(case)
        await s.flush()
        cid = str(case.case_file_id)
        await s.commit()
    r = await client.post(
        "/v1/intake/guided-answers",
        json={
            "case_file_id": cid,
            "has_secondary_coverage": True,
            "secondary_coverage_detail": "spouse plan via Cigna",
            "plan_effective_date": "2026-01-01",
            "all_plan_year_eobs_confirmed": True,
            "has_sibling_claims": True,
            "sibling_claim_date": "2026-03-14",
        },
    )
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cid)))
        ).scalar_one()
    cov = case.coverage or {}
    assert cov["has_secondary_coverage"] is True
    assert cov["plan_effective_date"] == "2026-01-01"
    assert cov["all_plan_year_eobs_confirmed"] is True
    assert cov["has_sibling_claims"] is True
