"""Materiality machinery + deterministic disclosure tiers (Sprint C, DL-85).

ONE home for the money/percentage thresholds so no magic numbers live elsewhere:

  * ``AUDIT_FLAG`` ($25 / 5%) — the DL-72 cross-validation / "is this discrepancy worth
    flagging in the audit" bar (Brock 2026-06-26). ``benefits_context`` imports it.
  * ``USER_CHASE`` ($100 / 10%) — the higher bar for asking the USER to go hunt down a
    missing document (DL-85, Brock 2026-07-03). We don't send someone digging through a
    shoebox for a $30 swing.

Plus a pure ``disclosure_tier`` function (0–3): the model NEVER picks its own confidence —
this deterministic mapping does, from range width vs the thresholds, input completeness,
and cross-validation status. And a generic ``compute_range`` for "compute the answer across
plausible values of a missing input" (priors live in ``missing_data_priors``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialityThresholds:
    """A gap is material when it exceeds ``abs_floor`` (absolute dollars), OR exceeds BOTH
    ``abs_tol`` AND ``pct`` (fraction of the larger magnitude). The abs_floor guarantees a
    large dollar gap can't be masked by the percentage test; the abs_tol guards against
    pennies of proportional drift tripping the flag."""

    abs_floor: float
    pct: float
    abs_tol: float = 1.0


# DL-72 (Brock 2026-06-26): cross-validation / audit-flag threshold. $25 floor + 5%.
AUDIT_FLAG = MaterialityThresholds(abs_floor=25.0, pct=0.05, abs_tol=1.0)
# DL-85 (Brock 2026-07-03): the bar for asking the USER to chase a missing input. $100 / 10%.
USER_CHASE = MaterialityThresholds(abs_floor=100.0, pct=0.10, abs_tol=1.0)


def is_material(spread: float, base: float, thresholds: MaterialityThresholds) -> bool:
    """True if a ``spread`` (dollar gap / range width) is material against ``base`` (the
    larger magnitude in play) under ``thresholds``."""
    spread = abs(spread)
    base = max(abs(base), 1.0)
    return spread > thresholds.abs_floor or (
        spread > thresholds.abs_tol and (spread / base) > thresholds.pct
    )


# --- disclosure tiers 0–3 (DL-85) --------------------------------------------
DISCLOSURE_TIER_LABELS: dict[int, str] = {
    0: "grounded",  # complete data / immaterial uncertainty — state plainly, disclose nothing
    1: "note",  # minor (audit-flag-level) uncertainty — mention it, no action needed
    2: "disclose",  # material uncertainty or a cross-validation discrepancy — surface it prominently
    3: "chase",  # a missing document would materially change the answer — ask the user to find it
}


def disclosure_tier(
    range_width: float,
    base: float,
    *,
    missing_inputs: Iterable[str] = (),
    cross_validation_material: bool = False,
    benchmark_substitution: bool = False,
) -> int:
    """Deterministic 0–3 disclosure tier. Inputs are the computed result's range width vs
    the USER_CHASE/AUDIT_FLAG thresholds, whether required inputs are missing, and whether
    cross-validation disagreed materially. Pure — the audit's confidence is a function of
    the data, never the model's self-report.

    ``benchmark_substitution`` (Brock 2026-08-22, §2.5): ANY benchmark substitution in the
    basis forces Tier 3 — full pattern, range only, never a point — regardless of width."""
    if benchmark_substitution:
        return 3
    has_missing = bool(list(missing_inputs))
    audit = is_material(range_width, base, AUDIT_FLAG)
    chase = is_material(range_width, base, USER_CHASE)
    if chase and has_missing:
        return 3  # a specific missing document could collapse a chase-sized range — ask
    if chase or cross_validation_material:
        return 2  # material uncertainty or a real discrepancy — disclose prominently
    if audit:
        return 1  # minor uncertainty worth a note
    return 0  # grounded


# --- range computation over plausible values of a missing input --------------
@dataclass(frozen=True)
class RangeResult:
    """The computed answer across plausible values of a missing input: (low, high, base),
    with the derived width. ``base`` is the answer at the prior's best-guess value."""

    low: float
    high: float
    base: float
    width: float
    input_key: str | None = None

    def to_dict(self) -> dict:
        return {
            "low": self.low,
            "high": self.high,
            "base": self.base,
            "width": self.width,
            "input_key": self.input_key,
        }


def compute_range(
    values: Iterable[float],
    compute_fn: Callable[[float], float],
    *,
    base_value: float | None = None,
    input_key: str | None = None,
) -> RangeResult:
    """Run ``compute_fn`` over each plausible ``values`` and return (low, high, base, width).
    ``base_value`` (the prior's best guess) fixes ``base``; without it, base is the median
    result. Generic on purpose — the caller supplies how a candidate input maps to a dollar
    result; the plausible values come from ``missing_data_priors``."""
    results = sorted(float(compute_fn(v)) for v in values)
    if not results:
        return RangeResult(0.0, 0.0, 0.0, 0.0, input_key)
    low, high = results[0], results[-1]
    base = float(compute_fn(base_value)) if base_value is not None else results[len(results) // 2]
    return RangeResult(
        low=round(low, 2),
        high=round(high, 2),
        base=round(base, 2),
        width=round(high - low, 2),
        input_key=input_key,
    )
