"""CO-12C.1 — PlanLibrary tests (DL-73).

Gating rule proven: a stored entry's benefit_design contains ONLY benefit-design
keys (no identifier, no per-person *_met). Plus: no silent prior-year carry-forward;
confirm increments confidence + writes through to coverage; reject forks a new entry.

DB tests use the configured test Postgres (conftest create_all) + the seeded dev user.
Each uses a unique payer so rows don't collide across tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth.dev_user import DEV_USER_ID
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.plan_library import PlanLibraryEntry
from app.services import plan_library as plan_lib
from app.services.plan_library import BENEFIT_DESIGN_KEYS, strip_identifiers
from app.sources.adapters.plan_library import PlanLibrary

_DIRTY = {
    "deductible_amount": 2000,
    "copay_specialist": 40,
    "coinsurance_percent": 20,
    # identifiers + per-person state that MUST NOT survive:
    "member_id": "ABC123456",
    "name": "Jane Doe",
    "subscriber": "Jane Doe",
    "group_number": "GRP-9",
    "dob": "1990-01-01",
    "account_number": "ACCT-9999",
    "claim_id": "CLM-1",
    "address": "1 Main St",
    "deductible_met": 500,
    "oop_max_met": 1200,
    "notes": "free text about the member",
}


# --- the gating PHI rule (pure) --------------------------------------------
def test_strip_identifiers_keeps_only_benefit_keys():
    clean = strip_identifiers(_DIRTY)
    assert set(clean) <= BENEFIT_DESIGN_KEYS
    # identifiers + per-person amounts dropped
    for forbidden in (
        "member_id",
        "name",
        "subscriber",
        "group_number",
        "dob",
        "account_number",
        "claim_id",
        "address",
        "notes",
        "deductible_met",
        "oop_max_met",
    ):
        assert forbidden not in clean
    # benefit terms kept
    assert clean["deductible_amount"] == 2000
    assert clean["copay_specialist"] == 40


def test_propose_payload_shape():
    entry = PlanLibraryEntry(
        plan_library_id=uuid4(),
        payer="Aetna",
        plan_name="Choice POS II",
        plan_year=2026,
        benefit_design={"deductible_amount": 2000, "copay_specialist": 40},
        confidence=2,
    )
    payload = plan_lib.propose(entry)
    assert payload["payer"] == "Aetna"
    assert payload["plan_year"] == 2026
    assert "Choice POS II" in payload["summary"]
    assert "$2,000" in payload["summary"]
    assert payload["benefit_design"]["copay_specialist"] == 40


# --- gating rule proven on a DB round-trip ---------------------------------
@pytest.mark.asyncio
async def test_stored_entry_phi_stripped_round_trip():
    pid = uuid4()
    async with AsyncSessionLocal() as s:
        s.add(
            PlanLibraryEntry(
                plan_library_id=pid,
                payer="PhiTestPayer",
                plan_name="RoundTrip",
                plan_year=2026,
                benefit_design=strip_identifiers(_DIRTY),
            )
        )
        await s.commit()
    async with AsyncSessionLocal() as s:
        stored = (
            await s.execute(select(PlanLibraryEntry).where(PlanLibraryEntry.plan_library_id == pid))
        ).scalar_one()
    keys = set(stored.benefit_design)
    assert keys <= BENEFIT_DESIGN_KEYS
    assert not (keys & {"member_id", "name", "dob", "account_number", "claim_id", "deductible_met"})


# --- match: no silent prior-year carry-forward -----------------------------
@pytest.mark.asyncio
async def test_match_no_prior_year_carry_forward():
    async with AsyncSessionLocal() as s:
        s.add(
            PlanLibraryEntry(
                plan_library_id=uuid4(),
                payer="CarryFwdTest",
                plan_name="Open Access",
                plan_year=2025,
                benefit_design={"deductible_amount": 1500},
                confidence=3,
            )
        )
        await s.commit()
    async with AsyncSessionLocal() as s:
        prior = await plan_lib.match(s, "CarryFwdTest", None, "Open Access", 2026)
        same = await plan_lib.match(s, "CarryFwdTest", None, "Open Access", 2025)
    assert prior is None  # a prior year is NOT carried forward to a current-year claim
    assert same is not None and same.plan_year == 2025


@pytest.mark.asyncio
async def test_match_highest_confidence_wins():
    async with AsyncSessionLocal() as s:
        s.add_all(
            [
                PlanLibraryEntry(
                    plan_library_id=uuid4(),
                    payer="ConfTest",
                    plan_year=2026,
                    benefit_design={"deductible_amount": 1000},
                    confidence=1,
                ),
                PlanLibraryEntry(
                    plan_library_id=uuid4(),
                    payer="ConfTest",
                    plan_year=2026,
                    benefit_design={"deductible_amount": 3000},
                    confidence=5,
                ),
            ]
        )
        await s.commit()
    async with AsyncSessionLocal() as s:
        best = await plan_lib.match(s, "ConfTest", None, None, 2026)
    assert best is not None and best.confidence == 5
    assert best.benefit_design["deductible_amount"] == 3000


# --- confirm / reject -------------------------------------------------------
@pytest.mark.asyncio
async def test_confirm_writes_coverage_and_increments_confidence():
    async with AsyncSessionLocal() as s:
        case = CaseFile(user_id=DEV_USER_ID, status="open")
        entry = PlanLibraryEntry(
            plan_library_id=uuid4(),
            payer="ConfirmTest",
            plan_name="Gold",
            plan_year=2026,
            benefit_design={"deductible_amount": 2500, "copay_specialist": 50},
            confidence=1,
        )
        s.add_all([case, entry])
        await s.flush()
        cid, pid = case.case_file_id, entry.plan_library_id
        await plan_lib.confirm(s, entry, case)
        await s.commit()
    async with AsyncSessionLocal() as s:
        case = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
        entry = (
            await s.execute(select(PlanLibraryEntry).where(PlanLibraryEntry.plan_library_id == pid))
        ).scalar_one()
    assert case.coverage["deductible_amount"] == 2500
    assert case.coverage["copay_specialist"] == 50
    assert case.plan_current["plan_library_id"] == str(pid)
    assert entry.confidence == 2  # incremented


@pytest.mark.asyncio
async def test_reject_forks_new_entry_and_archives_prior():
    # Unique payer so the row count is isolated from other runs (the test DB persists
    # across runs — create_all, no truncate).
    payer = "ForkTest-" + uuid4().hex[:8]
    prior_ptr = {"plan_library_id": "prior", "payer": payer}
    async with AsyncSessionLocal() as s:
        case = CaseFile(user_id=DEV_USER_ID, status="open", plan_current=prior_ptr)
        entry = PlanLibraryEntry(
            plan_library_id=uuid4(),
            payer=payer,
            plan_name="Silver",
            plan_year=2026,
            benefit_design={"deductible_amount": 4000},
            confidence=1,
        )
        s.add_all([case, entry])
        await s.flush()
        cid = case.case_file_id
        await plan_lib.reject(s, entry, {"deductible_amount": 1000, "member_id": "LEAK"}, case)
        await s.commit()
    async with AsyncSessionLocal() as s:
        forks = list(
            (await s.execute(select(PlanLibraryEntry).where(PlanLibraryEntry.payer == payer)))
            .scalars()
            .all()
        )
        case = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
    assert len(forks) == 2  # original + fork (not overwritten)
    fork = next(f for f in forks if f.benefit_design.get("deductible_amount") == 1000)
    assert "member_id" not in fork.benefit_design  # PHI stripped on the fork
    assert case.coverage["deductible_amount"] == 1000
    assert prior_ptr in case.plan_history


# --- adapter ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_plan_library_adapter_returns_confirmed_design():
    async with AsyncSessionLocal() as s:
        case = CaseFile(
            user_id=DEV_USER_ID,
            status="open",
            coverage={"deductible_amount": 1800, "member_id": "SHOULD_NOT_LEAK"},
            plan_current={"plan_library_id": str(uuid4()), "payer": "AdapterTest"},
        )
        s.add(case)
        await s.flush()
        cid = case.case_file_id
        await s.commit()
    res = await PlanLibrary().get_coverage(str(cid))
    assert res.provenance.adapter == "PlanLibrary"
    assert res.data["coverage"]["deductible_amount"] == 1800
    assert "member_id" not in res.data["coverage"]  # adapter returns design keys only
    assert res.provenance.confidence == 0.85  # a confirmed design
