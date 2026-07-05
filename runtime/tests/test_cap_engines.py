"""Per-population cap engines + year-versioned constants (Sprint F). Table-driven cases per
regime, the fail-loud missing-year path, the Medicaid range-over-missing-income path, and the
BenefitsContext.get_cap regime→engine wiring."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources import benefits_context
from app.sources.cap_engines import compute_cap
from app.sources.plan_constants import (
    CapConstantNotLoaded,
    available_years,
    lookup,
    missing_constant_finding,
)

AS_OF = date(2026, 7, 1)
COV = {"plan_year": 2026}


def _claims(*amounts):
    return [
        {"eob": {"amount_applied_to_oop": a, "date_of_service": "2026-03-01"}} for a in amounts
    ]


# --- constants registry ---
def test_lookup_and_fail_loud():
    assert lookup("medicare_traditional", "part_d_oop_cap", 2026).amount == 2100.0
    assert lookup("tricare_va", "champva_catastrophic_cap", 2026).amount == 3000.0
    # A structurally-present but value-pending row still returns (loaded=False).
    ma = lookup("medicare_advantage", "in_network_moop", 2026)
    assert ma.amount is None and ma.loaded is False
    # A year that isn't loaded raises — never carries forward.
    with pytest.raises(CapConstantNotLoaded):
        lookup("medicare_traditional", "part_d_oop_cap", 2027)
    assert available_years("medicare_traditional", "part_d_oop_cap") == [2026]


def test_missing_constant_finding_shape():
    f = missing_constant_finding("medicare_traditional", "part_d_oop_cap", 2027)
    assert f["category"] == "cap_constant_not_loaded"
    assert f["facts"]["plan_year"] == 2027


# --- cap engines: table-driven ---
@pytest.mark.parametrize(
    "regime,claims,coverage,expect_cap,expect_over,expect_excess",
    [
        ("medicare_traditional", _claims(1500), COV, 2100.0, False, 0.0),
        ("medicare_traditional", _claims(1500, 1000), COV, 2100.0, True, 400.0),
        ("tricare_va", _claims(2900), COV, 3000.0, False, 0.0),
        ("tricare_va", _claims(3500), COV, 3000.0, True, 500.0),
        ("medicaid", _claims(3000), {"plan_year": 2026, "household_income": 50000}, 2500.0, True, 500.0),
        ("medicare_advantage", _claims(9000), {"plan_year": 2026, "oop_max_amount": 8000}, 8000.0, True, 1000.0),
    ],
)
def test_cap_engines(regime, claims, coverage, expect_cap, expect_over, expect_excess):
    r = compute_cap(regime, claims, coverage, AS_OF)
    assert r is not None
    assert r.cap_amount == expect_cap
    assert r.over_cap is expect_over
    assert r.excess == expect_excess
    assert (r.finding_spec is not None) is expect_over
    if expect_over:
        assert r.finding_spec["category"] == "cost_sharing_cap_exceeded"


def test_regimes_without_a_cap_engine_return_none():
    for regime in ("commercial", "self_pay", "dual_qmb"):
        assert compute_cap(regime, _claims(500), COV, AS_OF) is None


def test_medicaid_ranges_over_missing_income():
    r = compute_cap("medicaid", _claims(3000), COV, AS_OF)
    assert r.cap_range is not None
    assert r.missing_inputs == ["household_income"]
    assert r.disclosure_tier == 3  # chase household income (span crosses USER_CHASE)
    assert r.over_cap is False  # can't declare over-cap without the income


def test_missing_year_fails_loud_with_finding():
    r = compute_cap("medicare_traditional", _claims(1000), {"plan_year": 2027}, AS_OF)
    assert r.cap_amount is None
    assert r.finding_spec["category"] == "cap_constant_not_loaded"


def test_ma_moop_missing_when_no_coverage_moop():
    r = compute_cap("medicare_advantage", _claims(9000), COV, AS_OF)
    assert r.cap_amount is None
    assert "in_network_moop" in r.missing_inputs


def test_plan_year_assumed_when_not_captured():
    r = compute_cap("medicare_traditional", _claims(1000), {}, AS_OF)  # no plan_year
    assert r.plan_year == 2026
    assert any("assumed to be calendar year" in a for a in r.assumptions)


# --- BenefitsContext wiring ---
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


async def test_benefits_context_get_cap_selects_engine():
    uid = await _dev_user_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=uid,
            status="open",
            coverage={"plan_year": 2026},
            eobs=_claims(1500, 1000),  # $2,500 cost-share vs the $2,100 Part D cap
        )
        s.add(cf)
        await s.commit()
        cfid = str(cf.case_file_id)

    result = await benefits_context.get_cap(cfid, "medicare_traditional", AS_OF)
    assert result is not None
    assert result.cap_amount == 2100.0
    assert result.over_cap is True
    assert result.excess == 400.0
