"""Reconcile-first conflicting-data state (§A2 state 3 / script §5iii).

The discipline under test is the LADDER: Tyndale explains, gives its own computed answer,
asks for ONE input only when that input would actually settle it, and routes to the
provider/plan ONLY when both are exhausted. "Call your provider" is computed by the state
machine — it can never be reached by authoring copy in a different order.
"""

from __future__ import annotations

import pytest

from app.agents.reconcile import (
    BILLED_VS_ALLOWED,
    DIFFERENCE_CATEGORIES,
    GROSS_VS_NET,
    TIMING,
    UNEXPLAINED,
    classify_difference,
    plan_reconcile,
)


def _facts(readings: dict, deltas: dict) -> dict:
    return {"readings": readings, "deltas": deltas, "as_of": "2026-07-31"}


# --- (b) difference category -------------------------------------------------
def test_timing_when_a_reading_is_absent_for_the_disputed_metric():
    readings = {
        "computed": {"deductible_applied": 1200.0, "oop_applied": 2000.0},
        "eob_stated": {"deductible_applied": 900.0, "oop_applied": None},
        "coverage_stated": {"deductible_applied": None, "oop_applied": None},
    }
    deltas = {"deductible_applied": {"spread": 300.0, "values": {"computed": 1200.0, "eob_stated": 900.0}}}
    assert classify_difference(readings, deltas) == TIMING


def test_billed_vs_allowed_when_only_one_metric_disagrees():
    readings = {
        "computed": {"deductible_applied": 1000.0, "oop_applied": 2000.0},
        "eob_stated": {"deductible_applied": 1000.0, "oop_applied": 1500.0},
        "coverage_stated": {"deductible_applied": 1000.0, "oop_applied": 1500.0},
    }
    deltas = {
        "deductible_applied": {"spread": 0.0, "values": {"computed": 1000.0, "eob_stated": 1000.0}},
        "oop_applied": {"spread": 500.0, "values": {"computed": 2000.0, "eob_stated": 1500.0}},
    }
    assert classify_difference(readings, deltas) == BILLED_VS_ALLOWED


def test_gross_vs_net_when_both_metrics_differ_by_a_similar_ratio():
    readings = {
        "computed": {"deductible_applied": 1000.0, "oop_applied": 2000.0},
        "eob_stated": {"deductible_applied": 800.0, "oop_applied": 1600.0},
        "coverage_stated": {"deductible_applied": 800.0, "oop_applied": 1600.0},
    }
    deltas = {
        "deductible_applied": {"spread": 200.0, "values": {"computed": 1000.0, "eob_stated": 800.0}},
        "oop_applied": {"spread": 400.0, "values": {"computed": 2000.0, "eob_stated": 1600.0}},
    }
    assert classify_difference(readings, deltas) == GROSS_VS_NET


def test_never_guesses_a_cause():
    """No disagreement, or a shape that fits nothing → 'unexplained', never a made-up cause."""
    assert classify_difference({}, {}) == UNEXPLAINED
    assert classify_difference({"computed": {}}, {"deductible_applied": {"spread": 0}}) == UNEXPLAINED
    assert all(c in DIFFERENCE_CATEGORIES for c in (TIMING, GROSS_VS_NET, BILLED_VS_ALLOWED, UNEXPLAINED))


# --- the ladder (the point of this state) -----------------------------------
_TWO_PRESENT_ONE_MISSING = _facts(
    {
        "computed": {"deductible_applied": 1200.0, "oop_applied": 2000.0},
        "eob_stated": {"deductible_applied": 900.0, "oop_applied": 2000.0},
        "coverage_stated": {"deductible_applied": None, "oop_applied": 2000.0},
    },
    {"deductible_applied": {"spread": 300.0, "values": {"computed": 1200.0, "eob_stated": 900.0}}},
)

_ALL_THREE_DISAGREE = _facts(
    {
        "computed": {"deductible_applied": 1200.0, "oop_applied": 2000.0},
        "eob_stated": {"deductible_applied": 900.0, "oop_applied": 1800.0},
        "coverage_stated": {"deductible_applied": 600.0, "oop_applied": 1500.0},
    },
    {
        "deductible_applied": {
            "spread": 600.0,
            "values": {"computed": 1200.0, "eob_stated": 900.0, "coverage_stated": 600.0},
        }
    },
)


def test_a_names_both_figures_with_their_sources():
    plan = plan_reconcile(_TWO_PRESENT_ONE_MISSING, completeness_confirmed=True)
    assert len(plan.figures) == 2
    assert {f["source"] for f in plan.figures} == {"computed", "eob_stated"}
    assert all(f["label"] and f["value"] is not None for f in plan.figures)  # never a bare number


def test_d_asks_one_input_and_that_alone_ends_the_ladder():
    """A single missing reading is resolvable → ask for it, and DON'T send them to the phone."""
    plan = plan_reconcile(_TWO_PRESENT_ONE_MISSING, completeness_confirmed=False)
    assert plan.ask_input == "your plan's Summary of Benefits (SBC)"
    assert plan.last_resort is False
    assert plan.rungs == ["explain", "ask_one_input"]


def test_c_conclusive_answer_ends_the_ladder_without_asking_or_calling():
    """Complete EOB set + a computed figure = Tyndale has the answer. No ask, no call."""
    plan = plan_reconcile(_ALL_THREE_DISAGREE, completeness_confirmed=True)
    assert plan.confidence == "high"
    assert plan.computed_value == 1200.0
    assert plan.ask_input is None
    assert plan.last_resort is False
    assert plan.rungs == ["explain"]


def test_e_last_resort_only_when_c_and_d_are_both_exhausted():
    """The ONLY path to "call your provider": no conclusive computed answer AND no single
    input that would resolve it."""
    plan = plan_reconcile(_ALL_THREE_DISAGREE, completeness_confirmed=False)
    assert plan.confidence == "provisional"
    assert plan.ask_input is None
    assert plan.last_resort is True
    assert plan.rungs == ["explain", "last_resort"]


def test_last_resort_never_renders_while_an_ask_would_resolve_it():
    """The regression this state exists to prevent: flag-and-send-off. Across every
    completeness state, an answerable ask suppresses the provider routing."""
    for confirmed in (True, False, None):
        plan = plan_reconcile(_TWO_PRESENT_ONE_MISSING, completeness_confirmed=confirmed)
        assert plan.last_resort is False, f"sent the user to the phone with an open ask ({confirmed})"
        assert "last_resort" not in plan.rungs


def test_ladder_order_is_structural_not_authored():
    """rungs always starts at explain and only grows — a caller can't reorder into a
    call-first flow."""
    for facts in (_TWO_PRESENT_ONE_MISSING, _ALL_THREE_DISAGREE):
        for confirmed in (True, False):
            rungs = plan_reconcile(facts, completeness_confirmed=confirmed).rungs
            assert rungs[0] == "explain"
            if "last_resort" in rungs:
                assert rungs.index("last_resort") == len(rungs) - 1
                assert "ask_one_input" not in rungs  # mutually exclusive by construction


def test_engine_finding_carries_the_difference_category():
    """benefits_context writes difference_category into the finding facts, so the user-facing
    state explains WHY rather than only that."""
    from datetime import date

    from app.sources.benefits_context import cross_validate

    cv = cross_validate(
        computed={"deductible_applied": 1200.0, "oop_applied": 2000.0},
        eob_stated={"deductible_applied": 400.0, "oop_applied": 900.0},
        coverage_stated={"deductible_met": 400.0, "oop_max_met": 900.0},
        as_of=date(2026, 7, 31),
    )
    assert cv.agreement is False and cv.finding_spec is not None
    assert cv.finding_spec["facts"]["difference_category"] in DIFFERENCE_CATEGORIES


@pytest.mark.parametrize("key", ["reconcile.explain", "reconcile.ask_one_input", "reconcile.last_resort"])
def test_registry_keys_exist(key):
    from app.agents.context_loader import load_orchestration_registry

    assert key in load_orchestration_registry()
