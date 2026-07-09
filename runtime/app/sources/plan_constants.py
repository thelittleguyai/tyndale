"""Year-versioned plan-constant registry (Sprint F).

A ``(regime, constant_name, plan_year) → PlanConstant`` table for the per-population cap
engines. Every value carries as_of + source; numbers the memo didn't give are seeded as
``amount=None`` with a ``TODO(brock-content)`` note so the structure is ready for the real
figure without a code change.

Fail loud, never carry forward: a lookup for a plan_year that isn't loaded raises
``CapConstantNotLoaded`` (the caller emits a "cap constants for <year> not yet loaded"
finding) rather than silently reusing last year's number (mirrors DL-73's no-silent-carry).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanConstant:
    """A single cap/limit. ``amount`` is None when the value is not yet loaded (the row
    exists so the engine can range/chase rather than crash). ``unit`` is 'usd' or
    'fraction' (e.g. Medicaid's 0.05 of household income)."""

    amount: float | None
    unit: str
    as_of: str
    source: str
    note: str = ""

    @property
    def loaded(self) -> bool:
        return self.amount is not None


class CapConstantNotLoaded(Exception):
    """Raised when no constant exists for (regime, name, plan_year). Never fall back to a
    different year — the caller turns this into a finding."""

    def __init__(self, regime: str, name: str, plan_year: int) -> None:
        self.regime, self.name, self.plan_year = regime, name, plan_year
        super().__init__(f"cap constants for {name} ({regime}, {plan_year}) not yet loaded")


# (regime, constant_name, plan_year) -> PlanConstant.
PLAN_CONSTANTS: dict[tuple[str, str, int], PlanConstant] = {
    # Given by the Batch-1 memo:
    ("medicare_traditional", "part_d_oop_cap", 2026): PlanConstant(
        2100.0, "usd", "2026-07-03", "Batch-1 memo (IRA Part D out-of-pocket cap, 2026)"
    ),
    ("va_champva", "champva_catastrophic_cap", 2026): PlanConstant(
        3000.0, "usd", "2026-07-03", "Batch-1 memo (CHAMPVA catastrophic cap)"
    ),
    # 'medicaid' is a cap-FAMILY key shared by medicaid_ffs + medicaid_mco (both carry the same
    # 5%-of-household-income federal cap) — the cap engine routes either regime here.
    ("medicaid", "household_cost_share_cap_pct", 2026): PlanConstant(
        0.05, "fraction", "2026-07-03", "Batch-1 memo (Medicaid 5%-of-household-income cap)",
        "5% of household income per quarter/month depending on state; needs household income input",
    ),
    # Structure present, value pending (memo named the cap but not the number):
    ("tricare", "tricare_catastrophic_cap", 2026): PlanConstant(
        None, "usd", "2026-07-03", "Batch-1 memo",
        "TODO(brock-content): TRICARE catastrophic cap amount (varies by beneficiary category)",
    ),
    ("medicare_advantage", "in_network_moop", 2026): PlanConstant(
        None, "usd", "2026-07-03", "CMS annual MA MOOP maximum",
        "TODO(brock-content): CMS 2026 MA in-network MOOP maximum; the plan-specific MOOP "
        "comes from the member's EOB/SBC when available",
    ),
    # STLDI max duration (Brock 2026-07-06). STATE-DEPENDENT + re-verifiable — never hardcoded:
    # the federal 4-month rule is under non-enforcement since 2025-08-07 with litigation stayed, so
    # the effective limit is per-state. amount=None → the engine ranges/chases rather than assert.
    ("stldi", "max_duration_months", 2026): PlanConstant(
        None, "months", "2026-07-06", "Brock memo 2026-07-06",
        "TODO(brock-content): state-dependent STLDI max duration; federal 4-month cap under "
        "non-enforcement since 2025-08-07 (litigation stayed) — verify the effective limit per state",
    ),
}


def lookup(regime: str, name: str, plan_year: int) -> PlanConstant:
    """The constant for (regime, name, plan_year), or raise CapConstantNotLoaded. A row with
    ``amount=None`` still returns (it's 'loaded structurally, value TODO'); only a truly
    absent year raises."""
    key = (regime, name, plan_year)
    if key not in PLAN_CONSTANTS:
        raise CapConstantNotLoaded(regime, name, plan_year)
    return PLAN_CONSTANTS[key]


def available_years(regime: str, name: str) -> list[int]:
    return sorted(y for (r, n, y) in PLAN_CONSTANTS if r == regime and n == name)


def missing_constant_finding(regime: str, name: str, plan_year: int) -> dict:
    """Finding spec for a not-yet-loaded cap constant (fail loud, don't carry forward)."""
    return {
        "finding_type": "data_consistency",
        "category": "cap_constant_not_loaded",
        "subagent_source": "cap_engine",
        "voice_tier": "A",
        "facts": {
            "regime": regime,
            "constant_name": name,
            "plan_year": plan_year,
            "available_years": available_years(regime, name),
        },
        "recommendation": {
            "action": f"Load the {name} cap constant for {plan_year} before applying this cap.",
            "reasoning": (
                f"Cap constants for {name} ({regime}) are not loaded for {plan_year}. Tyndale "
                "does not reuse a different year's figure — the cap is left uncomputed and "
                "disclosed rather than silently carried forward."
            ),
        },
    }
