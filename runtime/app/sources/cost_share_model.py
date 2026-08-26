"""Standard in-network cost-share arithmetic + the rung-2 range (SBC-gate removal).

Phil's ruling on the 2026-08-17 sweep: an audit COMPLETES when provider-side analysis
stands — missing coverage terms qualify the cost-sharing figure (X3 tiers), they do not
gate completion. This module supplies the deterministic piece: what `tyndale_computed`
honestly IS when coverage inputs are missing — a RANGE swept over the Sprint-C priors
(`missing_data_priors`, Brock's data drop pending) through the standard
deductible-then-coinsurance model:

    member = ded_hit + coinsurance * (anchor - ded_hit),  ded_hit = min(anchor, ded_remaining)
    bounded to [0, anchor]

This is arithmetic, not judgment — the judgment lives in the priors' values (Brock's) and
in the disclosure tier that names what's missing. Copay/OOP-cap nuance is absorbed by the
range: the low sweep includes deductible-already-met (a mid-year reality), the high sweep
full-deductible-first. The anchor is the payer's ALLOWED amount when the EOB states one
(the correct cost-share base), degrading to billed when it doesn't — recorded, so the
disclosure can say which.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sources.missing_data_priors import MISSING_DATA_PRIORS, missing_cost_share_inputs


@dataclass(frozen=True)
class Rung2Range:
    low: float
    base: float
    high: float
    anchor: float
    anchor_kind: str  # "allowed" | "billed"
    missing_inputs: list[str] = field(default_factory=list)
    model: str = "standard_deductible_coinsurance"
    # True when any prior CONSUMED by this range is still placeholder-flagged (Phil's
    # ruling 2026-08-18): the caller suppresses the user-visible range and renders point
    # form until Brock's researched values land. Stated coverage values never set this.
    placeholder_basis: bool = False

    @property
    def is_point(self) -> bool:
        return self.low == self.high


def member_cost_share(anchor: float, deductible_remaining: float, coinsurance: float) -> float:
    """One evaluation of the standard model, bounded to [0, anchor]."""
    anchor = max(float(anchor), 0.0)
    ded_hit = min(anchor, max(float(deductible_remaining), 0.0))
    member = ded_hit + float(coinsurance) * (anchor - ded_hit)
    return round(min(max(member, 0.0), anchor), 2)


def rung2_range(anchor: float, coverage: dict | None, *, anchor_kind: str) -> Rung2Range:
    """Sweep the model over what's known + the priors for what isn't.

    deductible_remaining candidates: 0.0 is ALWAYS plausible (deductible already met —
    a mid-year reality no document in hand disproves); the plan deductible joins it when
    coverage states one, the prior's grid when it doesn't. Coinsurance: the stated value
    when present, the prior's grid when missing. The base combo uses the priors' best
    guesses (or stated values), so `base` is the single most defensible point.
    """
    cov = coverage or {}
    missing = missing_cost_share_inputs(coverage)
    placeholder_basis = False

    stated_ded = cov.get("deductible_amount")
    if stated_ded is not None:
        ded_amounts = [float(stated_ded)]
        ded_base_amount = float(stated_ded)
    else:
        prior = MISSING_DATA_PRIORS["deductible_amount"]
        ded_amounts = list(prior.plausible_values())
        ded_base_amount = prior.base
        placeholder_basis = placeholder_basis or prior.placeholder
    # deductible_met (checklist item 2, Brock image-3): the classic load-bearing unknown.
    # Stated → ded_remaining is EXACT per amount candidate (amount − met, floored at 0) and
    # the "maybe already met" 0.0 guess drops out — this is what collapses the spread.
    # Unstated → 0.0 stays in the sweep (a mid-year reality no document in hand disproves).
    stated_met = cov.get("deductible_met")
    if stated_met is not None:
        met = max(float(stated_met), 0.0)
        ded_candidates = sorted({max(0.0, a - met) for a in ded_amounts})
        ded_base = max(0.0, ded_base_amount - met)
    else:
        ded_candidates = [0.0, *ded_amounts]
        ded_base = ded_base_amount

    stated_coins = cov.get("coinsurance_percent")
    if stated_coins is not None:
        coins_candidates = [float(stated_coins)]
        coins_base = float(stated_coins)
    else:
        prior = MISSING_DATA_PRIORS["coinsurance_percent"]
        coins_candidates = prior.plausible_values()
        coins_base = prior.base
        placeholder_basis = placeholder_basis or prior.placeholder

    # A STATED out-of-pocket max caps every evaluation: member owes at most what remains of
    # the cap (max − met when met is stated, the full max when it isn't — met ≥ 0 always).
    # Never swept from priors: the cap only tightens on real data, per the tier contract.
    oop_cap: float | None = None
    stated_oop = cov.get("oop_max_amount")
    if stated_oop is not None:
        stated_oop_met = cov.get("oop_max_met")
        oop_cap = (
            max(0.0, float(stated_oop) - max(float(stated_oop_met), 0.0))
            if stated_oop_met is not None
            else float(stated_oop)
        )

    def _capped(value: float) -> float:
        return round(min(value, oop_cap), 2) if oop_cap is not None else value

    results = sorted(
        _capped(member_cost_share(anchor, d, c))
        for d in ded_candidates
        for c in coins_candidates
    )
    return Rung2Range(
        low=results[0],
        base=_capped(member_cost_share(anchor, ded_base, coins_base)),
        high=results[-1],
        anchor=round(float(anchor), 2),
        anchor_kind=anchor_kind,
        missing_inputs=missing,
        placeholder_basis=placeholder_basis,
    )
