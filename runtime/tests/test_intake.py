"""Phase CO-1A — guided intake wizard tests.

USE_REAL_AUTH=false in tests, so all calls run as the seeded dev user. Each test
creates its OWN fresh case file and passes case_file_id explicitly, so the shared
test DB (no per-test truncation) can't make tests order-dependent.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.ingestion.extract_documents import extract_insurance_card_from_text


async def _dev_user_id() -> uuid.UUID:
    """The seeded dev user's id (any case belongs to them in tests)."""
    async with AsyncSessionLocal() as s:
        any_case = (await s.execute(select(CaseFile).limit(1))).scalar_one_or_none()
        if any_case is not None:
            return any_case.user_id
    # No case yet — resolve_dev_user creates the row.
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _fresh_case(**fields) -> str:
    """Insert an isolated case for the dev user; return its id."""
    uid = await _dev_user_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=uid,
            status="open",
            intake_status=fields.pop("intake_status", "not_started"),
            intake_current_step=fields.pop("intake_current_step", None),
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


# --------------------------------------------------------------------------- #
# Gating signals (state drives the frontend redirect)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_new_user_redirected_to_intake_welcome(client: AsyncClient):
    cfid = await _fresh_case(intake_status="not_started")
    r = await client.get("/v1/intake/state", params={"case_file_id": cfid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intake_status"] == "not_started"  # != complete → gate redirects
    assert body["current_step"] == "welcome"


@pytest.mark.asyncio
async def test_returning_complete_user_skips_intake(client: AsyncClient):
    cfid = await _fresh_case(intake_status="complete", intake_current_step="complete")
    r = await client.get("/v1/intake/state", params={"case_file_id": cfid})
    assert r.json()["intake_status"] == "complete"  # gate lets them through to dashboard


@pytest.mark.asyncio
async def test_returning_mid_wizard_resumes_at_current_step(client: AsyncClient):
    cfid = await _fresh_case(intake_status="in_progress", intake_current_step="benefits")
    body = (await client.get("/v1/intake/state", params={"case_file_id": cfid})).json()
    assert body["intake_status"] == "in_progress"
    assert body["current_step"] == "benefits"


@pytest.mark.asyncio
async def test_save_and_exit_preserves_state(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        "/v1/intake/step/coverage-details/manual-entry",
        json={"case_file_id": cfid, "payer": "Aetna", "member_id": "W123456789"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["current_step"] == "benefits"  # advanced past coverage-details
    # Re-entry (a fresh GET) shows the persisted progress + data.
    body = (await client.get("/v1/intake/state", params={"case_file_id": cfid})).json()
    assert body["current_step"] == "benefits"
    assert body["captured_data"]["coverage"]["payer_name"] == "Aetna"
    assert body["captured_data"]["coverage"]["member_id"] == "W123456789"


# --------------------------------------------------------------------------- #
# Manual entry + skip semantics
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_manual_entry_deductible_persists_to_case_file_coverage(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        "/v1/intake/step/deductible/manual-entry",
        json={"case_file_id": cfid, "deductible_total": 2000, "deductible_met": 500},
    )
    assert r.status_code == 200, r.text
    cf = await _case(cfid)
    assert cf.coverage["deductible_amount"] == 2000
    assert cf.coverage["deductible_met"] == 500


@pytest.mark.asyncio
async def test_skip_step_advances_without_persisting_step_data(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post("/v1/intake/step/oop-max/skip", json={"case_file_id": cfid})
    assert r.status_code == 200, r.text
    assert r.json()["current_step"] == "bills"  # advanced past oop-max
    cf = await _case(cfid)
    assert (cf.coverage or {}).get("oop_max_amount") is None  # nothing persisted for the step


# --------------------------------------------------------------------------- #
# Insurance-card low-confidence confirmation (P1)
# --------------------------------------------------------------------------- #
def test_low_confidence_insurance_card_extraction_returns_confirmation_prompt():
    # "ID: ..." (not "Member ID:") + an unknown payer → weak (0.60) matches.
    fields = extract_insurance_card_from_text("ACME Health Co\nID: A12345678\nGRP: 5000")
    prompts = fields.confirmations()
    member = next((p for p in prompts if p["field"] == "member_id"), None)
    assert member is not None, prompts
    assert member["confidence"] < 0.85
    assert member["read_value"] == "A12345678"
    assert "A12345678" in member["prompt"]


def test_high_confidence_insurance_card_extraction_persists_silently():
    fields = extract_insurance_card_from_text(
        "Aetna\nMember ID: W987654321\nGroup Number: 70123\nPlan: Aetna Choice POS II"
    )
    cov = fields.high_confidence_coverage()
    assert cov["payer_name"].lower().startswith("aetna")
    assert cov["member_id"] == "W987654321"
    assert not fields.confirmations()  # all strong → nothing to confirm


# --------------------------------------------------------------------------- #
# Visit context + completion
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_visit_context_stores_to_case_file_visit_context_field(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        "/v1/intake/visit-context",
        json={"case_file_id": cfid, "visit_context": "I went to the ER with chest pain"},
    )
    assert r.status_code == 200, r.text
    cf = await _case(cfid)
    assert cf.visit_context == "I went to the ER with chest pain"


@pytest.mark.asyncio
async def test_complete_requires_at_least_one_bill_OR_coverage_data(client: AsyncClient):
    cfid = await _fresh_case()
    # Neither a bill nor coverage data → blocked.
    blocked = await client.post("/v1/intake/complete", json={"case_file_id": cfid})
    assert blocked.status_code == 422, blocked.text
    # Add coverage data → completion allowed.
    await client.post(
        "/v1/intake/step/deductible/manual-entry",
        json={"case_file_id": cfid, "deductible_total": 1500, "deductible_met": 0},
    )
    ok = await client.post("/v1/intake/complete", json={"case_file_id": cfid})
    assert ok.status_code == 200, ok.text
    assert ok.json()["intake_status"] == "complete"


@pytest.mark.asyncio
async def test_completion_summary_lists_missing_items(client: AsyncClient):
    cfid = await _fresh_case()
    await client.post(
        "/v1/intake/step/coverage-details/manual-entry",
        json={"case_file_id": cfid, "payer": "Cigna", "member_id": "U555"},
    )
    body = (await client.post("/v1/intake/complete", json={"case_file_id": cfid})).json()
    assert body["missing_items"]  # bills, EOB, visit-context, OOP, deductible still missing
    assert any("bill" in m.lower() for m in body["missing_items"])
