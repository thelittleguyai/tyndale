"""Materiality thresholds + deterministic disclosure tiers (Sprint C, DL-85). Property-style
boundary cases at the $25/5% (AUDIT_FLAG) and $100/10% (USER_CHASE) lines, the range math,
and the pure tier function — the model never picks its own confidence, this does."""

from __future__ import annotations

import pytest

from app.sources.materiality import (
    AUDIT_FLAG,
    DISCLOSURE_TIER_LABELS,
    USER_CHASE,
    MaterialityThresholds,
    compute_range,
    disclosure_tier,
    is_material,
)


def test_constant_sets_are_distinct():
    assert (AUDIT_FLAG.abs_floor, AUDIT_FLAG.pct) == (25.0, 0.05)
    assert (USER_CHASE.abs_floor, USER_CHASE.pct) == (100.0, 0.10)


@pytest.mark.parametrize(
    "spread,base,thresholds,expected",
    [
        # AUDIT_FLAG $25 absolute floor (strict >), tested on a large base so pct can't fire.
        (25.01, 5000, AUDIT_FLAG, True),
        (25.0, 5000, AUDIT_FLAG, False),
        (24.99, 5000, AUDIT_FLAG, False),
        # AUDIT_FLAG 5% (strict >), with the $1 abs-tol guard satisfied.
        (5.01, 100, AUDIT_FLAG, True),
        (5.0, 100, AUDIT_FLAG, False),
        # $1 abs-tol guard: a sub-$1 gap never trips even at a huge percentage.
        (0.5, 1.0, AUDIT_FLAG, False),
        # USER_CHASE $100 absolute floor.
        (100.01, 5000, USER_CHASE, True),
        (99.99, 5000, USER_CHASE, False),
        # USER_CHASE 10%.
        (10.01, 100, USER_CHASE, True),
        (10.0, 100, USER_CHASE, False),
        # A $30 gap is AUDIT material but NOT USER_CHASE material (the whole point).
        (30, 5000, AUDIT_FLAG, True),
        (30, 5000, USER_CHASE, False),
    ],
)
def test_is_material_boundaries(spread, base, thresholds, expected):
    assert is_material(spread, base, thresholds) is expected


def test_is_material_negative_spread_uses_magnitude():
    assert is_material(-30, 5000, AUDIT_FLAG) is True


@pytest.mark.parametrize(
    "width,base,missing,cv,expected",
    [
        (0, 1, [], False, 0),  # grounded
        (30, 5000, [], False, 1),  # audit-material only → note
        (0, 1, [], True, 2),  # cross-validation discrepancy → disclose
        (150, 5000, [], False, 2),  # chase-material but nothing to chase → disclose
        (150, 5000, ["deductible_amount"], False, 3),  # chase-material + a missing doc → chase
        (30, 5000, ["deductible_amount"], False, 1),  # missing but sub-chase width → still note
    ],
)
def test_disclosure_tier(width, base, missing, cv, expected):
    assert disclosure_tier(width, base, missing_inputs=missing, cross_validation_material=cv) == expected


def test_disclosure_tier_is_monotonic_in_severity():
    grounded = disclosure_tier(0, 1)
    note = disclosure_tier(30, 5000)
    disclose = disclosure_tier(150, 5000)
    chase = disclosure_tier(150, 5000, missing_inputs=["deductible_amount"])
    assert grounded < note < disclose < chase
    assert {grounded, note, disclose, chase} <= set(DISCLOSURE_TIER_LABELS)


def test_compute_range():
    # Member owes min(bill, deductible) on a $3,000 bill across the deductible priors.
    r = compute_range([500, 2000, 8000], lambda d: min(3000, d), base_value=2000, input_key="deductible_amount")
    assert (r.low, r.high, r.base, r.width) == (500.0, 3000.0, 2000.0, 2500.0)
    assert r.input_key == "deductible_amount"


def test_compute_range_empty_is_degenerate():
    r = compute_range([], lambda v: v)
    assert (r.low, r.high, r.width) == (0.0, 0.0, 0.0)


def test_thresholds_are_frozen():
    with pytest.raises(Exception):
        MaterialityThresholds(abs_floor=1, pct=1).abs_floor = 2  # type: ignore[misc]
