"""Feedback IDOR + recovered-money poisoning (audit 2026-08-27 item 1): POST /v1/feedback
must reject a case the caller doesn't own (404, anti-enumeration), and the confirmed-recovered
aggregate must count only the case owner's own outcome reports."""

import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent
from app.sources.record import confirmed_recovered_by_case
from tests.test_thread_bridge import _upload_new_case


def _event(case_id: str, amount: float = 500.0) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_file_id": case_id,
        "feedback_type": "outcome_report",
        "outcome": {"resolved": "yes", "amount_saved": amount},
    }


async def _plant_victim_case() -> str:
    """A case belonging to SOMEONE ELSE (no API path creates one cross-tenant)."""
    from app.db.models.users import User

    async with AsyncSessionLocal() as s:
        victim = User(user_id=uuid.uuid4(), email=f"victim-{uuid.uuid4().hex[:10]}@idor.test")
        s.add(victim)
        await s.flush()
        cf = CaseFile(user_id=victim.user_id, status="audit_complete")
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


@pytest.mark.asyncio
async def test_cross_tenant_feedback_is_404_and_writes_nothing(client: AsyncClient):
    victim_case = await _plant_victim_case()
    r = await client.post("/v1/feedback", json=_event(victim_case, 9999.0))
    assert r.status_code == 404
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(victim_case))
            )
        ).scalar_one()
        assert cf.last_outcome_check_at is None  # the recency clock was not bumped
        rows = (
            await s.execute(
                select(FeedbackEvent).where(
                    FeedbackEvent.case_file_id == uuid.UUID(victim_case)
                )
            )
        ).scalars().all()
        assert rows == []  # nothing persisted against the victim
        # and the victim's recovered tally is untouched
        recovered = await confirmed_recovered_by_case(
            s, [uuid.UUID(victim_case)], cf.user_id
        )
        assert recovered == {}


@pytest.mark.asyncio
async def test_owner_feedback_still_works(client: AsyncClient):
    case_id, _ = await _upload_new_case(client)
    r = await client.post("/v1/feedback", json=_event(case_id, 120.0))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_foreign_row_is_excluded_from_the_owner_aggregate(client: AsyncClient):
    """A row poisoned in before the fix (owner's case, someone else's user_id) never
    reaches the owner's recovered tally — defense in depth on the read."""
    case_id, _ = await _upload_new_case(client)
    async with AsyncSessionLocal() as s:
        owner_id = (
            await s.execute(
                select(CaseFile.user_id).where(
                    CaseFile.case_file_id == uuid.UUID(case_id)
                )
            )
        ).scalar_one()
        s.add(
            FeedbackEvent(
                case_file_id=uuid.UUID(case_id),
                user_id=uuid.uuid4(),  # NOT the owner
                feedback_type="outcome_report",
                improvement_consent=False,
                payload={"outcome": {"resolved": "yes", "amount_saved": 9999.0}},
            )
        )
        await s.commit()
        poisoned = await confirmed_recovered_by_case(s, [uuid.UUID(case_id)], owner_id)
        assert poisoned == {}  # foreign row filtered out
        unfiltered = await confirmed_recovered_by_case(s, [uuid.UUID(case_id)])
        assert unfiltered  # sanity: the row IS there; only the owner filter excludes it
