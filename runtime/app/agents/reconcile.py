"""Conflicting-data reconcile-first state (Brock §A2 state 3 / script §5iii).

The engine already cross-validates the accumulator three ways and writes ONE
``accumulator_discrepancy`` finding (benefits_context, DL-72 / $25-5% AUDIT_FLAG). What was
missing is the USER-FACING state — and, critically, the DISCIPLINE around it.

THE LADDER IS A STATE MACHINE, NOT COPY ORDER. Tyndale does not flag-and-send-off:

    (a) name the two conflicting figures and their sources        — always
    (b) explain the difference CATEGORY                            — always
    (c) give Tyndale's independently computed answer + confidence  — always
    (d) ask for ONE missing input — ONLY when that single input would resolve the ambiguity
    (e) route to the provider/plan — ONLY when (c) and (d) are BOTH exhausted

``plan_reconcile`` returns the rungs to render. ``last_resort`` is computed, never authored
into the copy order: a caller cannot render "call your provider" while Tyndale still has an
answer or a question that would settle it.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Difference categories (§5iii's "gross vs net, billed vs allowed, timing"). The engine's
# readings/deltas are classified into one so the explanation names WHY the figures differ
# rather than just that they do.
GROSS_VS_NET = "gross_vs_net"
BILLED_VS_ALLOWED = "billed_vs_allowed"
TIMING = "timing"
UNEXPLAINED = "unexplained"

DIFFERENCE_CATEGORIES = (GROSS_VS_NET, BILLED_VS_ALLOWED, TIMING, UNEXPLAINED)

_SOURCE_LABELS = {
    "computed": "Tyndale's own reconstruction from your EOBs",
    "eob_stated": "the figure your EOB states",
    "coverage_stated": "the figure on your plan/card",
}


class ReconcilePlan(NamedTuple):
    """Which rungs render, and the facts they render with."""

    category: str
    figures: list[dict]  # [{source, label, value}] — the conflicting readings, named
    computed_value: float | None
    confidence: str  # high | provisional
    ask_input: str | None  # the ONE input that would resolve it, else None
    last_resort: bool  # (e) — computed, never authored

    @property
    def rungs(self) -> list[str]:
        out = ["explain"]
        if self.ask_input:
            out.append("ask_one_input")
        if self.last_resort:
            out.append("last_resort")
        return out


def classify_difference(readings: dict, deltas: dict) -> str:
    """The difference CATEGORY for a discrepancy (§5iii(b)).

    * timing            — the readings are consistent in shape but one is stale (a reading is
                          absent for a metric the others carry, i.e. a snapshot taken earlier).
    * gross_vs_net      — one reading is a near-multiple/offset of another on the SAME metric
                          in a way that tracks the plan-paid vs member-paid split.
    * billed_vs_allowed — the deductible metric agrees while OOP disagrees (or vice versa):
                          a classic allowed-amount-vs-billed-amount application difference.
    * unexplained       — anything else. NEVER guessed into a specific cause.
    """
    computed = readings.get("computed") or {}
    eob = readings.get("eob_stated") or {}
    coverage = readings.get("coverage_stated") or {}

    disagreeing = [m for m, d in (deltas or {}).items() if (d or {}).get("spread")]
    if not disagreeing:
        return UNEXPLAINED

    # A metric present in one reading and absent in another is a snapshot-age difference.
    for m in disagreeing:
        present = [r for r in (computed, eob, coverage) if r.get(m) is not None]
        if len(present) < 3 and any(r.get(m) is None for r in (computed, eob, coverage)):
            return TIMING

    # Only one of the two metrics disagrees → the two figures are applying different bases.
    if len(disagreeing) == 1 and len(deltas) > 1:
        return BILLED_VS_ALLOWED

    # Both metrics disagree by a similar ratio → one side is gross, the other net.
    ratios = []
    for m in disagreeing:
        vals = [v for v in ((deltas.get(m) or {}).get("values") or {}).values() if v]
        if len(vals) >= 2 and min(vals):
            ratios.append(max(vals) / min(vals))
    if len(ratios) >= 2 and max(ratios) - min(ratios) < 0.15:
        return GROSS_VS_NET
    return UNEXPLAINED


def _figures(readings: dict, deltas: dict) -> list[dict]:
    """The conflicting figures, each named with its SOURCE (§5iii(a)) — the worst metric."""
    worst = max(
        (deltas or {}).items(), key=lambda kv: (kv[1] or {}).get("spread") or 0, default=(None, {})
    )
    metric, detail = worst
    if metric is None:
        return []
    return [
        {"source": src, "label": _SOURCE_LABELS.get(src, src), "value": val, "metric": metric}
        for src, val in ((detail or {}).get("values") or {}).items()
    ]


def _resolving_input(readings: dict, deltas: dict) -> str | None:
    """The ONE input that would actually settle the ambiguity, or None (§5iii(d)).

    Only a genuinely decisive input qualifies: when exactly one of the three readings is
    MISSING for the disputed metric, obtaining it breaks the tie. When all three are present
    and disagree, no single document resolves it — asking would just cost the user a trip."""
    worst = max(
        (deltas or {}).items(), key=lambda kv: (kv[1] or {}).get("spread") or 0, default=(None, {})
    )
    metric = worst[0]
    if metric is None:
        return None
    missing = [
        src
        for src in ("computed", "eob_stated", "coverage_stated")
        if (readings.get(src) or {}).get(metric) is None
    ]
    if len(missing) != 1:
        return None
    return {
        "eob_stated": "the EOB for this visit",
        "coverage_stated": "your plan's Summary of Benefits (SBC)",
        "computed": "the remaining EOBs for this plan year",
    }.get(missing[0])


def plan_reconcile(facts: dict[str, Any], *, completeness_confirmed: bool | None = None) -> ReconcilePlan:
    """Build the ladder from an accumulator_discrepancy finding's ``facts``.

    ENFORCEMENT: ``last_resort`` is True ONLY when Tyndale has no conclusive answer (the
    computed reconstruction is provisional because the EOB set isn't confirmed complete) AND
    no single input would resolve the ambiguity. Otherwise (c) or (d) is the end of the
    ladder and the provider/plan line does not render."""
    readings = facts.get("readings") or {}
    deltas = facts.get("deltas") or {}
    category = classify_difference(readings, deltas)
    figures = _figures(readings, deltas)
    ask = _resolving_input(readings, deltas)

    worst_metric = figures[0]["metric"] if figures else None
    computed_value = (readings.get("computed") or {}).get(worst_metric) if worst_metric else None
    # DL-86: an unconfirmed EOB set makes the reconstruction provisional, not authoritative.
    conclusive = computed_value is not None and bool(completeness_confirmed)
    confidence = "high" if conclusive else "provisional"

    return ReconcilePlan(
        category=category,
        figures=figures,
        computed_value=computed_value,
        confidence=confidence,
        ask_input=ask,
        last_resort=not conclusive and ask is None,
    )
