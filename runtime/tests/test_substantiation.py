"""Claim substantiation gate (Internal Analytics P0, §7). A claim publishes only when its sample
size clears the threshold; under threshold it is NOT PUBLISHABLE with the shortfall. The win-rate
claim hard-embeds its report-basis qualifier."""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient

from app.analytics.definitions import DEFINITIONS
from app.analytics.substantiation import CLAIMS, Claim, evaluate_claim, gate, to_markdown
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_daily import AnalyticsDaily

# An isolated far-past day so the all-time sum sees only what this test seeds (as_of excludes
# every other test's rollups, which live in 2018+).
_DAY = datetime.date(2015, 6, 1)


def test_gate_is_a_pure_threshold():
    assert gate(50, 100) == (False, 50)
    assert gate(100, 100) == (True, 0)
    assert gate(150, 100) == (True, 0)


def test_win_rate_claim_carries_the_hard_qualifier():
    assert CLAIMS["win_rate"].qualifier
    assert "reported" in CLAIMS["win_rate"].qualifier.lower()


async def _seed(numerator: float, denominator: float) -> None:
    async with AsyncSessionLocal() as s:
        s.add(AnalyticsDaily(
            metric_key="close_the_loop_rate", day=_DAY, numerator=numerator,
            denominator=denominator, value=numerator / denominator,
            definition=DEFINITIONS["close_the_loop_rate"].definition,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_gate_decides_publishability_against_seeded_evidence(client: AsyncClient):
    await _seed(30.0, 60.0)  # n=60 on an isolated far-past day
    async with AsyncSessionLocal() as s:
        under = await evaluate_claim(
            s, Claim("t", "{value}", "close_the_loop_rate", min_n=100), as_of=_DAY
        )
        over = await evaluate_claim(
            s, Claim("t", "{value}", "close_the_loop_rate", min_n=10), as_of=_DAY
        )
    # Same evidence (n=60), threshold decides.
    assert under["gate_status"] == "NOT PUBLISHABLE" and under["shortfall"] == 40  # 100 - 60
    assert under["n"] == 60.0 and under["denominator"] == 60.0
    assert "NOT PUBLISHABLE" in to_markdown(under) and "Shortfall" in to_markdown(under)
    assert over["gate_status"] == "PUBLISHABLE" and over["shortfall"] == 0
    assert over["value_display"].endswith("%")
    assert over["definition"]  # Rule 1: the definition always rides along
