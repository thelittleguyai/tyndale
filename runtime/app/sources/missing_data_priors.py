"""Plausible-value priors for missing audit inputs (Sprint C, DL-85).

When a required input is missing, the audit computes the answer across this input's
plausible range (see ``materiality.compute_range``) and discloses the resulting spread
rather than dead-ending. The numbers here are PLACEHOLDERS structured so Brock's researched
priors drop in as a data-only change.

TODO(brock-content: missing_data_spectrum_2026-07-03.md) — replace the low/base/high values
below with the researched priors; do not change the shape or the keys.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class InputPrior:
    """A plausible-value prior for one missing input. ``unit`` is 'usd' (a dollar amount)
    or 'fraction' (e.g. a 0.20 coinsurance). ``plausible_values`` are what the range
    computation sweeps; ``base`` is the best single guess.

    ``placeholder`` (2026-08-18, Phil's ruling): while True, any user-visible RANGE this
    prior feeds is SUPPRESSED — the rung-2 figure renders point-form only. Brock's
    researched table flips entries to False as they land, activating ranges per-entry
    with no code change. His data drop IS the activation switch."""

    low: float
    base: float
    high: float
    unit: str  # "usd" | "fraction"
    source: str  # provenance of the prior (placeholder until Brock's table lands)
    note: str = ""
    placeholder: bool = True
    # Per-entry provenance date from the tranche that set this entry (Brock 2026-08-18:
    # tranches land piecemeal, so provenance is per ENTRY, never per table).
    as_of: str | None = None

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
    # Sprint F: Medicaid's 5%-of-household-income cap needs household income, which intake
    # does not collect (TODO(phil-decision): add the intake question). Until then the cap is
    # ranged over this prior. Placeholder spread — TODO(brock-content).
    "household_income": InputPrior(
        low=20000.0, base=45000.0, high=120000.0, unit="usd",
        source="placeholder", note="annual household income for the Medicaid 5% cost-share cap",
    ),
}

# ── The receiving dock (Brock 2026-08-18, priors tranches) ──────────────────────────────
# Brock's table arrives in TRANCHES: JSON files under intelligence-layer/reference/priors/,
# each updating SOME entries. They merge PER ENTRY over the placeholders above at import
# (later files win per entry), carrying provenance (source, as_of) per entry. An entry flips
# live the moment its tranche says "placeholder": false; untouched siblings stay dark. The
# merge mutates MISSING_DATA_PRIORS IN PLACE so every module that imported the dict sees it.
_TRANCHE_DIR = "reference/priors"
_NUMERIC = ("low", "base", "high")


def _priors_dir() -> Path:
    override = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
    root = Path(override).resolve() if override else Path(__file__).resolve().parents[3] / "intelligence-layer"
    return root / _TRANCHE_DIR


def _merge_entry(current: InputPrior, patch: dict, *, source: str, as_of: str | None) -> InputPrior:
    fields: dict = {}
    for k in _NUMERIC:
        if k in patch:
            fields[k] = float(patch[k])
    if "unit" in patch and patch["unit"] in ("usd", "fraction"):
        fields["unit"] = patch["unit"]
    if "note" in patch:
        fields["note"] = str(patch["note"])
    fields["placeholder"] = bool(patch.get("placeholder", True))
    fields["source"] = str(patch.get("source") or source)
    fields["as_of"] = patch.get("as_of") or as_of
    merged = replace(current, **fields)
    if not merged.low <= merged.base <= merged.high:
        raise ValueError(f"prior must satisfy low <= base <= high: {merged}")
    return merged


def load_priors(target: dict[str, InputPrior] | None = None) -> dict[str, InputPrior]:
    """Merge every tranche file (sorted by name) into ``target`` (default: the live table),
    per entry, in place. Unknown keys are logged and skipped; a malformed file is logged and
    skipped — the placeholders stay dark rather than the runtime failing to import."""
    table = MISSING_DATA_PRIORS if target is None else target
    directory = _priors_dir()
    if not directory.is_dir():
        return table
    for path in sorted(directory.glob("*.json")):
        try:
            tranche = json.loads(path.read_text(encoding="utf-8"))
            source = str(tranche.get("source") or path.name)
            as_of = tranche.get("as_of")
            for key, patch in (tranche.get("entries") or {}).items():
                if key not in table:
                    log.warning("priors.unknown_entry", file=path.name, key=key)
                    continue
                if not isinstance(patch, dict):
                    continue
                table[key] = _merge_entry(table[key], patch, source=source, as_of=as_of)
        except Exception as exc:  # noqa: BLE001 — a bad tranche never breaks the runtime
            log.error("priors.tranche_rejected", file=path.name, error=str(exc))
    return table


load_priors()


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
