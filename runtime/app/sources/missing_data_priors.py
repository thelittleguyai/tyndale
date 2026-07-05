"""Plausible-value priors for missing audit inputs (Sprint C, DL-85).

When a required input is missing, the audit computes the answer across this input's
plausible range (see ``materiality.compute_range``) and discloses the resulting spread
rather than dead-ending. The numbers here are PLACEHOLDERS structured so Brock's researched
priors drop in as a data-only change.

TODO(brock-content: missing_data_spectrum_2026-07-03.md) — replace the low/base/high values
below with the researched priors; do not change the shape or the keys.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InputPrior:
    """A plausible-value prior for one missing input. ``unit`` is 'usd' (a dollar amount)
    or 'fraction' (e.g. a 0.20 coinsurance). ``plausible_values`` are what the range
    computation sweeps; ``base`` is the best single guess."""

    low: float
    base: float
    high: float
    unit: str  # "usd" | "fraction"
    source: str  # provenance of the prior (placeholder until Brock's table lands)
    note: str = ""

    def plausible_values(self) -> list[float]:
        """The values the range computation sweeps. A coarse low/base/high grid for now;
        Brock's table can supply a denser grid without any code change."""
        return sorted({self.low, self.base, self.high})

    def usd_span(self) -> float:
        """Dollar width of the prior (high - low) for usd inputs; 0.0 for fractions
        (a fraction's dollar impact depends on the bill, so it's not chase-sizeable alone)."""
        return round(self.high - self.low, 2) if self.unit == "usd" else 0.0


# PLACEHOLDER priors. TODO(brock-content: missing_data_spectrum_2026-07-03.md).
MISSING_DATA_PRIORS: dict[str, InputPrior] = {
    "deductible_amount": InputPrior(
        low=500.0, base=2000.0, high=8000.0, unit="usd",
        source="placeholder", note="individual medical deductible spread",
    ),
    "oop_max_amount": InputPrior(
        low=3000.0, base=8000.0, high=18000.0, unit="usd",
        source="placeholder", note="individual out-of-pocket maximum spread",
    ),
    "coinsurance_percent": InputPrior(
        low=0.10, base=0.20, high=0.40, unit="fraction",
        source="placeholder", note="member coinsurance share after deductible",
    ),
    "copay_specialist": InputPrior(
        low=20.0, base=50.0, high=100.0, unit="usd",
        source="placeholder", note="specialist visit copay",
    ),
    "copay_er": InputPrior(
        low=150.0, base=350.0, high=700.0, unit="usd",
        source="placeholder", note="emergency-room copay",
    ),
}

# Cost-share inputs the forward audit needs; absence of any of these is what the disclosure
# ladder may chase (only when the input's plausible span crosses USER_CHASE).
REQUIRED_COST_SHARE_INPUTS: tuple[str, ...] = (
    "deductible_amount",
    "oop_max_amount",
    "coinsurance_percent",
)


def missing_cost_share_inputs(coverage: dict | None) -> list[str]:
    """The REQUIRED_COST_SHARE_INPUTS absent from a coverage blob (value is None/missing)."""
    cov = coverage or {}
    return [k for k in REQUIRED_COST_SHARE_INPUTS if cov.get(k) is None]
