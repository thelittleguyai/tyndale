"""EOB-completeness confirmation (Sprint D, DL-86): the pure summary + the confirm
endpoints + the cross-validation gating (agreeing readings aren't called 'corroborated'
until the user confirms the EOB set is complete)."""

from __future__ import annotations

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources.benefits_context import cross_validate
from app.sources.eob_completeness import summarize_eob_completeness


def _eob(date=None, patient=None):
    d = {}
    if date:
        d["adjudication_date"] = date
    if patient:
        d["patient_name"] = patient
    return {"eob": d}


def test_summary_counts_span_and_question():
    eobs = [_eob("2026-01-15"), _eob("2026-03-20"), _eob("2026-06-02")]
    s = summarize_eob_completeness(eobs, {"plan_year": 2026})
    assert s.eob_count == 3
    assert s.plan_year == 2026
    assert (s.date_start, s.date_end) == ("2026-01-15", "2026-06-02")
    assert "3 EOBs this plan year" in s.question
    assert "Jan–Jun 2026" in s.question
    assert s.confirmed is None


def test_family_detection():
    s = summarize_eob_completeness([_eob("2026-01-01", "Jane Doe"), _eob("2026-02-01", "Kid Doe")], {})
    assert s.covers_family is True
    assert set(s.patient_names) == {"Jane Doe", "Kid Doe"}
    assert "covering 2 people" in s.question


def test_single_patient_is_not_family():
    s = summarize_eob_completeness([_eob("2026-01-01", "Jane Doe")], {})
    assert s.covers_family is False
    assert "none for family members" in s.question


def test_undated_and_confirmed_flag():
    s = summarize_eob_completeness([_eob(), _eob("2026-05-01")], {"all_plan_year_eobs_confirmed": True})
    assert s.undated_count == 1
    assert s.dated_count == 1
    assert s.confirmed is True


def test_cross_validation_corroboration_is_provisional_until_confirmed():
    computed = {"deductible_applied": 1000.0, "oop_applied": 1000.0}
    same = {"deductible_applied": 1000.0, "oop_applied": 1000.0}
    as_of = datetime.date(2026, 7, 1)
    unconfirmed = cross_validate(computed, same, {"deductible_met": 1000, "oop_max_met": 1000}, as_of)
    assert unconfirmed.agreement is True
    assert any("provisional" in a for a in unconfirmed.assumptions)
    confirmed = cross_validate(
        computed, same, {"deductible_met": 1000, "oop_max_met": 1000}, as_of,
        completeness_confirmed=True,
    )
    assert any("corroborated" in a for a in confirmed.assumptions)


# --- route tests ---
async def _dev_user_id() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        any_case = (await s.execute(select(CaseFile).limit(1))).scalar_one_or_none()
        if any_case is not None:
            return any_case.user_id
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _fresh_case(**fields) -> str:
    uid = await _dev_user_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status=fields.pop("status", "encounter_verified"), **fields)
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _status(cfid: str) -> str:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))
        ).scalar_one().status


async def test_eob_completeness_endpoints(client: AsyncClient):
    cfid = await _fresh_case(eobs=[_eob("2026-02-01"), _eob("2026-04-01")])
    r = await client.get(f"/v1/audit/{cfid}/eob-completeness")
    assert r.status_code == 200
    body = r.json()
    assert body["eob_count"] == 2
    assert body["confirmed"] is None

    # Confirm complete → flag set, and an awaiting case would be unblocked.
    ok = await client.post(f"/v1/audit/{cfid}/eob-completeness/confirm", json={"all_uploaded": True})
    assert ok.status_code == 200
    assert ok.json()["confirmed"] is True


async def test_not_all_uploaded_parks_case(client: AsyncClient):
    cfid = await _fresh_case(eobs=[_eob("2026-02-01")])
    r = await client.post(f"/v1/audit/{cfid}/eob-completeness/confirm", json={"all_uploaded": False})
    assert r.status_code == 200
    assert r.json()["confirmed"] is False
    assert await _status(cfid) == "awaiting_eob_confirmation"
