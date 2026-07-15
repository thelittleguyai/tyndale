"""Daily aggregation (Internal Analytics P0, §2) + Rule 1 (every rate names its denominator).

Rollups are computed on an isolated fixture day so other tests' events don't pollute the counts.
Rule 1 is enforced two ways: a MetricDef can't be constructed without a definition, and the
analytics_daily CHECK constraint refuses a row whose definition is blank."""

from __future__ import annotations

import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.analytics.definitions import DEFINITIONS, MetricDef
from app.analytics.rollup import rollup_day
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_daily import AnalyticsDaily
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.users import User

# An isolated day far from any real/other-test events.
_DAY = datetime.date(2019, 3, 14)
_NOON = datetime.datetime.combine(_DAY, datetime.time(12, 0), tzinfo=datetime.timezone.utc)


async def _a_user_id() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(User.user_id).limit(1))).scalar_one()


async def _seed(session, event_name: str, n: int, uid, props: dict | None = None) -> None:
    for _ in range(n):
        session.add(AnalyticsEvent(
            event_name=event_name, user_id=uid, occurred_at=_NOON, properties=props or {},
        ))


async def _row(metric_key: str) -> AnalyticsDaily | None:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(
                select(AnalyticsDaily)
                .where(AnalyticsDaily.metric_key == metric_key)
                .where(AnalyticsDaily.day == _DAY)
            )
        ).scalar_one_or_none()


# --- Rule 1 -----------------------------------------------------------------
def test_metricdef_requires_a_definition():
    with pytest.raises(ValueError):
        MetricDef("x", "   ", "count", None)  # blank definition → Rule 1 violation


def test_win_rate_definition_is_the_canonical_string():
    assert "outcomes REPORTED" in DEFINITIONS["win_rate"].definition
    assert "never" in DEFINITIONS["win_rate"].definition.lower()


@pytest.mark.asyncio
async def test_analytics_daily_rejects_blank_definition(client: AsyncClient):
    with pytest.raises(IntegrityError):
        async with AsyncSessionLocal() as s:
            s.add(AnalyticsDaily(metric_key="x", day=_DAY, numerator=1.0, definition="  "))
            await s.commit()


# --- aggregation correctness on a fixture day -------------------------------
@pytest.mark.asyncio
async def test_win_rate_and_pairing_on_a_fixture_day(client: AsyncClient):
    uid = await _a_user_id()
    async with AsyncSessionLocal() as s:
        # Isolate the fixture day from any prior run on the persisted local DB (CI is fresh).
        await s.execute(delete(AnalyticsEvent).where(AnalyticsEvent.occurred_at == _NOON))
        await s.execute(delete(AnalyticsDaily).where(AnalyticsDaily.day == _DAY))
        await s.commit()
        # 3 outcomes reported that day: 2 resolved (yes, partial), 1 no.
        await _seed(s, "outcome_reported", 2, uid, {"resolved": "yes", "amount_saved": 100.0})
        await _seed(s, "outcome_reported", 1, uid, {"resolved": "no", "amount_saved": 0.0})
        # close-the-loop: 2 issued, 1 satisfied.
        await _seed(s, "document_request_issued", 2, uid)
        await _seed(s, "document_request_satisfied", 1, uid)
        await s.commit()
        await rollup_day(s, _DAY)

    win = await _row("win_rate")
    assert win is not None
    assert win.numerator == 2.0 and win.denominator == 3.0  # 2 resolved / 3 reported
    assert abs(win.value - (2 / 3)) < 1e-9
    assert win.definition and not win.backfilled  # Rule 1 rides along; live (not backfilled)

    ctl = await _row("close_the_loop_rate")
    assert ctl.numerator == 1.0 and ctl.denominator == 2.0


@pytest.mark.asyncio
async def test_zero_denominator_yields_null_value_not_div_by_zero(client: AsyncClient):
    # A metric with no events that day: numerator 0, denominator 0, value None (never a crash).
    day = datetime.date(2018, 7, 1)
    async with AsyncSessionLocal() as s:
        await rollup_day(s, day)
        row = (
            await s.execute(
                select(AnalyticsDaily)
                .where(AnalyticsDaily.metric_key == "win_rate")
                .where(AnalyticsDaily.day == day)
            )
        ).scalar_one()
    assert row.numerator == 0.0 and row.denominator == 0.0 and row.value is None
