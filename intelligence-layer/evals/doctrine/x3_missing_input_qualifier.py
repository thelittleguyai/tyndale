"""X3 — incomplete-input figures carry a NAMING qualifier (contract per the draft).

THE CONTRACT
    For every user-facing computed figure whose computation consumed an incomplete input set
    (missing_inputs ≠ ∅ — the engine tracks these per DL-72/85):
      * a qualifier renders IN THE SAME VISUAL UNIT as the figure (same card/line — a
        footnote elsewhere fails `qualifier_detached`);
      * the qualifier NAMES at least the single most material missing input — "estimated"
        alone fails `generic_qualifier`;
      * the disclosure tier picks the form (cfg.X3_TIER_QUALIFIER): tier 0 forbids a
        qualifier outright (`qualifier_on_complete_figure` — hedging a complete number is its
        own failure), tier 1 wants the point form, tier ≥2 the range form
        ("between {low} and {high} until I see your {input}").

    Canonical failure (the draft's worked example):
        "What you should actually owe: $612.40"  rendered while the SBC is missing
        → FAIL: reasons missing_inputs_nonempty(sbc), no_qualifier_in_unit.

MECHANICS
    Pure + stdlib-only, X1's template. Figure input shape (built by the caller from real
    engine state — figures are DATA here, never re-derived):
        {"label": str, "value": float|str,
         "missing_inputs": [str, ...],          # [] when complete
         "tier": int,                           # disclosure tier 0..3
         "qualifier": {"text": str, "names": [str, ...], "same_unit": bool,
                       "form": "point"|"range"} | None}
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    import doctrine_config as cfg
except ImportError:
    from . import doctrine_config as cfg  # type: ignore[no-redef]


@dataclass
class X3Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    figures_checked: int = 0

    def summary(self) -> str:
        state = "PASS" if self.passed else "FAIL"
        parts = [f"X3 {state} ({self.figures_checked} figure(s))"]
        if self.reasons:
            parts.append("reasons: " + ", ".join(self.reasons))
        if self.notes:
            parts.append("notes: " + ", ".join(self.notes))
        return "; ".join(parts)


def _qualifier_names_an_input(qualifier: dict, missing: list[str]) -> bool:
    names = [str(n).strip().lower() for n in (qualifier.get("names") or []) if str(n).strip()]
    if not names:
        return False
    if all(n in cfg.X3_GENERIC_QUALIFIERS for n in names):
        return False  # "estimated" alone is not a name
    # Must name at least the most material missing input (list order = materiality, per the
    # engine's priors ordering). Substring match so "your plan's SBC" names "sbc".
    most_material = str(missing[0]).strip().lower()
    return any(most_material in n or n in most_material for n in names)


def check_x3(figures: list[dict]) -> X3Verdict:
    verdict = X3Verdict(passed=True, figures_checked=len(figures))
    if not figures:
        verdict.notes.append("no_figures (vacuous pass)")
        return verdict

    for fig in figures:
        label = str(fig.get("label") or "figure")
        missing = [str(m) for m in (fig.get("missing_inputs") or [])]
        tier = int(fig.get("tier") or (1 if missing else 0))
        qualifier = fig.get("qualifier")
        required_form = cfg.X3_TIER_QUALIFIER.get(tier, "range")

        if not missing:
            if qualifier is not None and required_form == "none":
                verdict.passed = False
                verdict.reasons.append(f"qualifier_on_complete_figure: {label}")
            continue

        verdict.notes.append(f"missing_inputs_nonempty({','.join(missing)}): {label}")
        if qualifier is None:
            verdict.passed = False
            verdict.reasons.append(f"no_qualifier_in_unit: {label}")
            continue
        if not qualifier.get("same_unit"):
            verdict.passed = False
            verdict.reasons.append(f"qualifier_detached: {label}")
        if not _qualifier_names_an_input(qualifier, missing):
            verdict.passed = False
            verdict.reasons.append(f"generic_qualifier: {label}")
        if required_form == "range" and qualifier.get("form") != "range":
            verdict.passed = False
            verdict.reasons.append(f"tier_{tier}_requires_range_form: {label}")
    return verdict
