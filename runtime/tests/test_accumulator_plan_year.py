"""Accumulator records the plan-year=calendar-year assumption + reflects it in confidence
(Phase 2.3). The plan-start month isn't captured, so the calendar-year assumption is a real
uncertainty that must show in provenance + lower confidence."""

from __future__ import annotations

from datetime import date

from app.sources.adapters.computed_from_uploaded_eobs import compute_accumulator


def test_plan_year_assumption_recorded_and_lowers_confidence():
    eobs = [
        {
            "eob": {
                "adjudication_date": "2026-02-01",
                "amount_applied_to_deductible": 100.0,
                "amount_applied_to_oop": 100.0,
            }
        }
    ]
    # coverage carries family structure → NO bucketing assumption, so the ONLY discount
    # beyond the base is the plan-year factor: 0.70 * usable(1.0) * 0.90 = 0.63.
    coverage = {
        "deductible_amount": 1000.0,
        "oop_max_amount": 5000.0,
        "family_deductible_amount": 2000.0,
    }
    result = compute_accumulator(eobs, coverage, date(2026, 3, 1), all_eobs_uploaded=True)

    assert result.data["plan_year"] == 2026
    assert any("plan year assumed to be calendar year 2026" in a for a in result.assumptions)
    assert result.confidence == 0.63  # base 0.70 * 1.0 usable * 0.90 plan-year factor
