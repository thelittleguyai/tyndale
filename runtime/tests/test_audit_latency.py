"""Audit latency (Item 2, 2026-07-07).

Measured on case e539735e: the finalize audit ran the three agents strictly sequentially
(BD 143s → MP 78s → LP 53s = 273s), with ZERO regenerations. Per DL-80 Math Person consumes
the pre-computed accumulator, not Bill Detective's output, so BD and MP are independent and now
run concurrently (critical path max(BD,MP)+LP instead of BD+MP+LP). These lock the concurrency
and the p50/p95 percentile signal surfaced on the admin System page."""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from app.agents import bill_detective, llm_health, math_person, orchestrator
from app.agents.audit_budget import AuditBudget
from app.agents.runner import RunResult


@pytest.mark.asyncio
async def test_bill_detective_and_math_person_run_concurrently(monkeypatch):
    events: list[tuple[str, float]] = []

    async def _bd(case_file_id, *, mode="diagnose", confirmations=None, session=None):
        events.append(("bd_start", time.monotonic()))
        await asyncio.sleep(0.2)
        events.append(("bd_end", time.monotonic()))
        return RunResult(final_text="bd-findings", tool_calls=[], usage={})

    async def _mp(case_file_id, *, accumulator=None, session=None):
        events.append(("mp_start", time.monotonic()))
        await asyncio.sleep(0.2)
        events.append(("mp_end", time.monotonic()))
        return RunResult(final_text="mp-numbers", tool_calls=[], usage={})

    async def _lp(case_file_id, bd_text, mp_text, *, session=None):
        # LP must receive BOTH upstreams — proves it still composes from the parallel pair.
        assert bd_text == "bd-findings" and mp_text == "mp-numbers"
        return RunResult(final_text="composed", tool_calls=[], usage={})

    monkeypatch.setattr(bill_detective, "run", _bd)
    monkeypatch.setattr(math_person, "run", _mp)
    monkeypatch.setattr(orchestrator.lead_planner, "compose_final", _lp)

    budget = AuditBudget(deadline=time.monotonic() + 600, regen_remaining=3)
    composed, stopped, stage_ms = await orchestrator._run_real_agents(
        str(uuid.uuid4()), None, [], budget
    )

    assert composed == "composed"
    assert stopped is False
    # Concurrency proof: each started before the other finished (their windows overlap).
    at = dict(events)
    assert at["bd_start"] < at["mp_end"]
    assert at["mp_start"] < at["bd_end"]
    # Wall-clock of the parallel phase is ~max (200ms), well under the sequential sum (~400ms).
    assert stage_ms["agents_parallel_wall_ms"] < 350


def test_audit_duration_percentiles_nearest_rank():
    llm_health._audit_durations.clear()
    for d in (10.0, 20.0, 30.0, 40.0, 100.0):
        llm_health.record_audit_run(duration_seconds=d, reason="complete", regens=0, path="foundry")
    p = llm_health.audit_duration_percentiles()
    assert p["count"] == 5
    assert p["p50_seconds"] == 30.0  # nearest-rank ceil(.50*5)=3 -> 3rd smallest
    assert p["p95_seconds"] == 100.0  # ceil(.95*5)=5 -> the max (a slow run shows in p95)


def test_audit_duration_percentiles_empty():
    llm_health._audit_durations.clear()
    assert llm_health.audit_duration_percentiles() == {
        "count": 0,
        "p50_seconds": None,
        "p95_seconds": None,
    }
