"""§2.5 tier-contract spot check (Brock 2026-08-22): tiers are COMPUTED, never authored,
and the Tranche-1 values produce the tier the contract promises. Run with -s to see the
rendered sample language for the debrief."""

from __future__ import annotations

from app.sources.cost_share_model import rung2_range
from app.sources.materiality import disclosure_tier


def test_tier1_tight_prior_inline_clause():
    # Coinsurance is the tight prior (0.19–0.20). On a $1,000 anchor the ~$10 swing is
    # honestly Tier 0 (below the $25 audit floor — the thresholds, not opinion); at a
    # $5,000 anchor the $50 swing crosses it → the Tier-1 inline note, no push.
    small = rung2_range(1000.0, {"deductible_amount": 0.0}, anchor_kind="allowed")
    assert disclosure_tier(small.high - small.low, small.base,
                           missing_inputs=small.missing_inputs) == 0
    rng = rung2_range(5000.0, {"deductible_amount": 0.0}, anchor_kind="allowed")
    width = rng.high - rng.low
    tier = disclosure_tier(width, rng.base, missing_inputs=rng.missing_inputs)
    assert rng.placeholder_basis is False  # Tranche 1 activated the basis
    assert tier == 1, (width, tier)
    print(f"\nTIER 1 sample: 'I assumed 20% coinsurance — the norm (KFF 2025); if yours "
          f"differs this moves about ${width / 5:.0f} per $1,000 of allowed charges.'")


def test_tier3_missing_deductible_computed_range_and_push():
    # No coverage at all: the deductible prior (0–2000) dominates → chase-sized swing with
    # named missing inputs → tier 3 (the ask), rendered as the computed range + one push.
    rng = rung2_range(1800.0, None, anchor_kind="allowed")
    width = rng.high - rng.low
    tier = disclosure_tier(width, rng.base, missing_inputs=rng.missing_inputs)
    assert rng.placeholder_basis is False
    assert tier == 3 and "deductible_amount" in rng.missing_inputs
    print(f"TIER 3 sample: 'Without your plan's deductible, your share could be "
          f"${rng.low:.0f}–${rng.high:.0f} — your SBC would pin this down.'")


def test_tier2_material_swing_without_a_chaseable_document():
    # A material computed swing with NO missing input named (e.g. cross-validation
    # disagreement) → tier 2: disclose prominently, no document chase.
    assert disclosure_tier(500.0, 1000.0, cross_validation_material=True) == 2
    print("TIER 2 sample: 'Your insurer's math and your plan's terms disagree by $500 — "
          "I've shown both and flagged it.'")


def test_tiers_are_computed_never_authored():
    # The tier function is pure arithmetic over width/base/flags — same inputs, same tier.
    args = (250.0, 900.0)
    assert disclosure_tier(*args, missing_inputs=["deductible_amount"]) == 3
    assert disclosure_tier(*args) == 2
    assert disclosure_tier(10.0, 900.0) == 0
