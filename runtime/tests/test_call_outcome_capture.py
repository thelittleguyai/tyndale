"""Call-mode outcome capture (deep review, finding 6).

"How did it go?" rendered three routes and recorded nothing — it deferred to the dashboard
follow-up, which fires ~14 days later and so loses everyone who answered in the moment.
Brock's spec calls this the outcome-capture denominator, so the tap now records.

The subtle part is what it must NOT do. A call outcome is not a case outcome:

- **It carries no money.** "They said they'd fix it" is a claim by the party we are auditing.
  Letting it reach `recovered_so_far` would put unconfirmed recoveries in the one number the
  §4 confirmed-only rule exists to protect.
- **It must not write an `outcome_report`.** The follow-up scan retires a case PERMANENTLY the
  moment one exists (`if outcome_exists is not None: continue`). Since none of the three routes
  resolves anything, an outcome_report here would delete the real question rather than defer it
  — we would never learn whether the call actually worked.

So the tap stamps the RECENCY clock (`last_outcome_check_at`), deferring the follow-up by its
window, and leaves permanent retirement to a genuine outcome report.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.analytics.events import REGISTRY
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent
from app.sources.record import _outcome_amount

ROUTES = ("fixing_it", "pushed_back", "left_message")


def _body(case_id: str, route: str, finding_id: str = "f-1") -> dict:
    return {
        "event_id": f"call-{case_id}-{finding_id}-{route}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_file_id": case_id,
        "response_id": finding_id,
        "feedback_type": "implicit_signal",
        "call_outcome": route,
    }


async def _open_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


async def _case(case_id: str) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()


# --- the event shape is what keeps money out ---------------------------------------------
def test_the_route_enum_is_registered_and_carries_no_money():
    """A call outcome may never grow an amount property — that is what makes it structurally
    incapable of moving the recovered tally."""
    spec = REGISTRY["call_outcome_recorded"]
    assert set(spec.props) == {"route"}, "call_outcome_recorded must carry the route ONLY"
    assert tuple(spec.props["route"].values) == ROUTES


# --- tap → recorded → follow-up deferred --------------------------------------------------
@pytest.mark.asyncio
async def test_a_route_tap_defers_the_dashboard_followup(client: AsyncClient):
    case_id = await _open_case(client)
    assert (await _case(case_id)).last_outcome_check_at is None

    r = await client.post("/v1/feedback", json=_body(case_id, "fixing_it"))
    assert r.status_code == 200, r.text
    assert (await _case(case_id)).last_outcome_check_at is not None, "follow-up clock unstamped"


@pytest.mark.asyncio
async def test_a_call_tap_never_writes_an_outcome_report(client: AsyncClient):
    """The load-bearing negative: an outcome_report would retire the follow-up FOREVER."""
    case_id = await _open_case(client)
    for route in ROUTES:
        r = await client.post("/v1/feedback", json=_body(case_id, route, finding_id=route))
        assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as s:
        reports = (
            await s.execute(
                select(FeedbackEvent)
                .where(FeedbackEvent.case_file_id == uuid.UUID(case_id))
                .where(FeedbackEvent.feedback_type == "outcome_report")
            )
        ).scalars().all()
    assert reports == [], "a call tap wrote an outcome_report — the real follow-up is now dead"


@pytest.mark.asyncio
async def test_a_call_tap_contributes_nothing_to_recovered(client: AsyncClient):
    """Asserted against the real accumulator: recovered needs resolved ∈ (yes, partial) AND an
    amount. A call outcome supplies neither."""
    case_id = await _open_case(client)
    await client.post("/v1/feedback", json=_body(case_id, "fixing_it"))

    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(FeedbackEvent).where(FeedbackEvent.case_file_id == uuid.UUID(case_id))
            )
        ).scalars().all()
    assert rows, "the tap wrote nothing at all"
    for row in rows:
        assert _outcome_amount(row.payload) is None


@pytest.mark.asyncio
async def test_every_route_is_accepted(client: AsyncClient):
    case_id = await _open_case(client)
    for route in ROUTES:
        r = await client.post("/v1/feedback", json=_body(case_id, route, finding_id=route))
        assert r.status_code == 200, f"{route}: {r.text}"


@pytest.mark.asyncio
async def test_an_unknown_route_is_rejected_rather_than_stored(client: AsyncClient):
    """Typed enum, not free text — an unrecognised route is a 422, never a row nobody can
    aggregate."""
    case_id = await _open_case(client)
    r = await client.post("/v1/feedback", json=_body(case_id, "went_great"))
    assert r.status_code == 422
