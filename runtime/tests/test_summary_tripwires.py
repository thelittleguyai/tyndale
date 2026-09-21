"""Deep review (2026-09-18): the WORST fabrication seam — a code bad enough that the Lead
Planner summary is regenerated, or thrown away — recorded no tripwire, so the human-review
queue's `canary` trigger never fired for exactly those cases. It does now, through an atomic
JSONB append (no read-modify-write on research_log)."""

from __future__ import annotations

import asyncio
import time
import uuid
from types import SimpleNamespace

import pytest

from app.agents import orchestrator
from app.agents.audit_budget import AuditBudget
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.review import queue as rq

_BILL_TEXT = "EMERGENCY DEPT VISIT 99284  TOTAL DUE 1,200.00"
_FABRICATED = "We reviewed your emergency visit. The bill also lists CPT 02417, which looks wrong."
_CLEAN = "We reviewed your emergency visit (CPT 99284) and the charge matches the record."


async def _case_with_bill() -> str:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        user = await resolve_dev_user(s)
        cf = CaseFile(
            user_id=user.user_id,
            status="audit_running",
            coverage={"deductible_amount": 2000, "oop_max_amount": 6000, "coinsurance_percent": 0.2},
            documents=[{"document_id": str(uuid.uuid4()), "document_type": "bill",
                        "extraction_status": "extracted", "ocr_text": _BILL_TEXT}],
        )
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _tripwires(cfid: str) -> list[dict]:
    async with AsyncSessionLocal() as s:
        return orchestrator.tripwire_entries(await s.get(CaseFile, uuid.UUID(cfid)))


def _budget(regens: int) -> AuditBudget:
    return AuditBudget(deadline=time.monotonic() + 600, regen_remaining=regens)


@pytest.mark.asyncio
async def test_a_regenerated_summary_records_a_tripwire_and_flags_the_canary(monkeypatch):
    async def compose_final(*a, **k):
        return SimpleNamespace(final_text=_CLEAN)

    monkeypatch.setattr(orchestrator.lead_planner, "compose_final", compose_final)
    cfid = await _case_with_bill()
    out = await orchestrator._ground_prose(cfid, _FABRICATED, _budget(1), "bd", "mp")
    assert out == _CLEAN  # the one retry fixed it

    entries = await _tripwires(cfid)
    assert [(e["which"], e["codes"]) for e in entries] == [("grounding_summary_regen", ["02417"])]
    assert entries[0]["kind"] == "tripwire" and entries[0]["at"]

    # …and that is what the review queue's canary trigger reads
    async with AsyncSessionLocal() as s:
        facts = await rq.gather_facts(s, await s.get(CaseFile, uuid.UUID(cfid)), "audit_complete", None)
    assert facts.canary_flag is True


@pytest.mark.asyncio
async def test_a_degraded_summary_records_a_tripwire_with_no_regen_left():
    cfid = await _case_with_bill()
    out = await orchestrator._ground_prose(cfid, _FABRICATED, _budget(0), "bd", "mp")
    assert out == ""  # no summary beats a fabricated code
    assert [(e["which"], e["codes"]) for e in await _tripwires(cfid)] == [
        ("grounding_summary_degraded", ["02417"])
    ]


@pytest.mark.asyncio
async def test_a_regen_that_still_fabricates_records_both(monkeypatch):
    async def compose_final(*a, **k):
        return SimpleNamespace(final_text=_FABRICATED)

    monkeypatch.setattr(orchestrator.lead_planner, "compose_final", compose_final)
    cfid = await _case_with_bill()
    assert await orchestrator._ground_prose(cfid, _FABRICATED, _budget(1), "bd", "mp") == ""
    assert [e["which"] for e in await _tripwires(cfid)] == [
        "grounding_summary_regen", "grounding_summary_degraded",
    ]


@pytest.mark.asyncio
async def test_a_clean_summary_records_nothing():
    cfid = await _case_with_bill()
    assert await orchestrator._ground_prose(cfid, _CLEAN, _budget(1), "bd", "mp") == _CLEAN
    assert await _tripwires(cfid) == []


@pytest.mark.asyncio
async def test_concurrent_appends_are_never_lost():
    """Item 7: research_log is appended with `coalesce(research_log,'[]') || :entry` in ONE
    UPDATE. The old read-modify-write (load the list, append in Python, write it back) lost
    entries when two writers overlapped."""
    cfid = await _case_with_bill()
    await asyncio.gather(*[
        orchestrator._append_tripwire(cfid, "grounding_drop", codes=[f"{i:05d}"], category="bundling")
        for i in range(12)
    ])
    entries = await _tripwires(cfid)
    assert len(entries) == 12 and {e["codes"][0] for e in entries} == {f"{i:05d}" for i in range(12)}

    async with AsyncSessionLocal() as s:  # it also joins a caller's transaction
        await orchestrator._append_tripwire(cfid, "translate_drop", codes=["02417"], session=s)
        await s.rollback()
    assert len(await _tripwires(cfid)) == 12  # rolled back with the caller
    async with AsyncSessionLocal() as s:
        await orchestrator._append_tripwire(cfid, "translate_drop", codes=["02417"], session=s)
        await s.commit()
    assert [e["which"] for e in await _tripwires(cfid)][-1] == "translate_drop"

    # a NULL log and an unknown case are both fine — and nothing raises
    async with AsyncSessionLocal() as s:
        cf = await s.get(CaseFile, uuid.UUID(cfid))
        cf.research_log = None
        await s.commit()
    await orchestrator._append_tripwire(cfid, "grounding_scrub")
    assert len(await _tripwires(cfid)) == 1
    await orchestrator._append_tripwire(str(uuid.uuid4()), "grounding_scrub")
