"""CO-12B wiring — the deterministic accumulator engine in the live audit path.

Covers the orchestrator seam (`_run_accumulator_cross_check` called from
finalize_audit / run_audit):

* material EOB disagreement during finalize -> ONE accumulator_discrepancy
  Finding (idempotent across re-finalize);
* readings in tolerance -> no finding;
* no uploaded EOB data -> the cross-check is skipped entirely (an all-zero
  reconstruction must not spuriously "disagree" with card-stated met values);
* the accumulator raising must NEVER fail the audit (log-and-continue);
* Math Person receives the computed reconstruction as injected message context.

Uses the conftest async client + the app's AsyncSessionLocal (same pattern as
test_e2e_mri.py); dates are anchored to the current plan year because the
engine filters EOBs to as_of's calendar year.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import math_person, orchestrator
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding

PLAN_YEAR = date.today().year


@pytest.fixture
def force_fixture_path(monkeypatch):
    """Force the fixture short-circuit regardless of the developer's .env.local
    (same pattern as test_e2e_mri.py)."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "use_real_claude", False)
    yield


def _eob(**kw) -> dict:
    base = {
        "adjudication_date": f"{PLAN_YEAR}-01-15",
        "date_of_service": None,
        "amount_applied_to_deductible": None,
        "amount_applied_to_oop": None,
        "deductible_ytd_stated": None,
        "oop_ytd_stated": None,
        "network_status": None,
    }
    base.update(kw)
    return base


async def _make_case(client: AsyncClient) -> str:
    files = {"file": ("bill.txt", b"%PDF-1.4 sample bill", "text/plain")}
    up = await client.post("/v1/upload", files=files)
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


async def _set_case_data(
    case_file_id: str, *, eobs: list[dict] | None = None, coverage: dict | None = None
) -> None:
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one()
        if eobs is not None:
            cf.eobs = eobs
        if coverage is not None:
            cf.coverage = coverage
        await s.commit()


async def _accumulator_findings(case_file_id: str) -> list[Finding]:
    async with AsyncSessionLocal() as s:
        return (
            (
                await s.execute(
                    select(Finding)
                    .where(Finding.case_file_id == UUID(case_file_id))
                    .where(Finding.category == "accumulator_discrepancy")
                )
            )
            .scalars()
            .all()
        )


# --- discrepancy finding during finalize --------------------------------------


@pytest.mark.asyncio
async def test_finalize_writes_discrepancy_finding_when_eobs_disagree(
    client: AsyncClient, force_fixture_path
) -> None:
    """Computed $500 vs EOB-stated $1,500 (material per DL-72) -> exactly one
    accumulator_discrepancy finding, surfaced in the finalize AuditResult, and
    idempotent across a re-finalize."""
    case_id = await _make_case(client)
    await _set_case_data(
        case_id,
        eobs=[
            _eob(
                amount_applied_to_deductible=500.0,
                amount_applied_to_oop=500.0,
                deductible_ytd_stated=1500.0,  # payer claims $1,000 more than computed
                oop_ytd_stated=500.0,
            )
        ],
        coverage={"deductible_amount": 2000.0, "all_plan_year_eobs_confirmed": True},
    )

    result = await orchestrator.finalize_audit(case_id)
    assert result.status == "complete"

    rows = await _accumulator_findings(case_id)
    assert len(rows) == 1, "expected exactly one accumulator_discrepancy finding"
    f = rows[0]
    assert f.finding_type == "payer_side"
    assert f.voice_tier == "A"
    assert f.subagent_source == "math_person"
    readings = f.facts["readings"]
    assert readings["computed"]["deductible_applied"] == 500.0
    assert readings["eob_stated"]["deductible_applied"] == 1500.0

    # Surfaced in the API projection alongside the fixture three-number finding.
    categories = [fo.category for fo in result.findings]
    assert "accumulator_discrepancy" in categories

    # Idempotent: re-finalizing must not duplicate the open finding.
    await orchestrator.finalize_audit(case_id)
    assert len(await _accumulator_findings(case_id)) == 1


@pytest.mark.asyncio
async def test_finalize_no_finding_when_readings_in_tolerance(
    client: AsyncClient, force_fixture_path
) -> None:
    """EOB-stated YTD matches the computed reconstruction -> agreement, no finding."""
    case_id = await _make_case(client)
    await _set_case_data(
        case_id,
        eobs=[
            _eob(
                amount_applied_to_deductible=500.0,
                amount_applied_to_oop=500.0,
                deductible_ytd_stated=500.0,
                oop_ytd_stated=500.0,
            )
        ],
        coverage={
            "deductible_amount": 2000.0,
            "deductible_met": 500.0,
            "oop_max_met": 500.0,
            "all_plan_year_eobs_confirmed": True,
        },
    )

    result = await orchestrator.finalize_audit(case_id)
    assert result.status == "complete"
    assert await _accumulator_findings(case_id) == []


@pytest.mark.asyncio
async def test_finalize_skips_accumulator_when_no_eobs(
    client: AsyncClient, force_fixture_path
) -> None:
    """No uploaded EOB data -> the cross-check is skipped: card-stated met values
    must NOT be flagged against an all-zero reconstruction the engine had no data
    to build (and the pre-existing fixture flow stays untouched)."""
    case_id = await _make_case(client)
    await _set_case_data(
        case_id,
        coverage={"deductible_amount": 2000.0, "deductible_met": 750.0, "oop_max_met": 750.0},
    )

    result = await orchestrator.finalize_audit(case_id)
    assert result.status == "complete"
    assert await _accumulator_findings(case_id) == []


# --- failure-safety ------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_completes_when_accumulator_raises(
    client: AsyncClient, force_fixture_path, monkeypatch
) -> None:
    """The accumulator must never fail an audit: get_accumulator raising is logged
    and swallowed; finalize still reaches audit_complete with the three numbers."""
    case_id = await _make_case(client)
    await _set_case_data(
        case_id,
        eobs=[_eob(amount_applied_to_deductible=500.0, deductible_ytd_stated=1500.0)],
    )

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("accumulator exploded")

    monkeypatch.setattr(orchestrator.benefits_context, "get_accumulator", _boom)

    result = await orchestrator.finalize_audit(case_id)
    assert result.status == "complete"
    assert result.audit is not None  # fixture three-number finding still assembled
    assert await _accumulator_findings(case_id) == []


# --- Math Person context injection ----------------------------------------------


@pytest.mark.asyncio
async def test_cross_check_returns_math_person_context(
    client: AsyncClient, force_fixture_path
) -> None:
    """The orchestrator helper returns the computed reconstruction as a compact
    context dict (data + confidence + assumptions) for Math Person."""
    case_id = await _make_case(client)
    await _set_case_data(
        case_id,
        eobs=[
            _eob(
                amount_applied_to_deductible=350.0,
                amount_applied_to_oop=375.0,
                deductible_ytd_stated=350.0,
                oop_ytd_stated=375.0,
            )
        ],
        coverage={"deductible_amount": 1000.0, "all_plan_year_eobs_confirmed": True},
    )

    ctx = await orchestrator._run_accumulator_cross_check(case_id)
    assert ctx is not None
    assert ctx["deductible_applied"] == 350.0
    assert ctx["oop_applied"] == 375.0
    assert ctx["eobs_counted"] == 1
    assert "confidence" in ctx and "assumptions" in ctx and "as_of" in ctx


@pytest.mark.asyncio
async def test_cross_check_returns_none_without_eobs(
    client: AsyncClient, force_fixture_path
) -> None:
    case_id = await _make_case(client)
    assert await orchestrator._run_accumulator_cross_check(case_id) is None


def test_math_person_message_includes_accumulator_context() -> None:
    """The injected accumulator lands in Math Person's user message; without it
    the message is unchanged."""
    ctx = {
        "as_of": f"{PLAN_YEAR}-06-01",
        "deductible_applied": 350.0,
        "oop_applied": 375.0,
        "confidence": 0.7,
        "assumptions": ["accumulator corroborated across the available readings"],
    }
    with_ctx = math_person._build_user_message("case-1", ctx)
    assert "PRE-COMPUTED ACCUMULATOR" in with_ctx
    assert "350.0" in with_ctx
    assert "do NOT write a duplicate" in with_ctx

    without_ctx = math_person._build_user_message("case-1")
    assert "PRE-COMPUTED ACCUMULATOR" not in without_ctx
