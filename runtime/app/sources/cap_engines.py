"""Per-population cost-sharing cap engines (Sprint F).

One pure function per regime that has a statutory/plan cap, following the CO-12B accumulator
pattern (pure, provenance/assumptions discipline, never fabricates). Each sums the member's
YTD cost-share from the normalized claims, looks up the regime's cap in the year-versioned
``plan_constants`` registry, and reports whether the member has been billed past the cap —
reusing the $25/5% materiality bar (AUDIT_FLAG) and the Sprint C disclosure tiers.

A cap that needs an input we don't collect (Medicaid's 5%-of-household-income cap) is
computed as a RANGE over the plausible-value priors rather than dead-ending — and the intake
question to collect it is flagged TODO(phil-decision).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.sources.case_data import as_float, parse_iso_date
from app.sources.materiality import (
    AUDIT_FLAG,
    DISCLOSURE_TIER_LABELS,
    compute_range,
    disclosure_tier,
    is_material,
)
from app.sources.missing_data_priors import MISSING_DATA_PRIORS
from app.sources.plan_constants import CapConstantNotLoaded, lookup, missing_constant_finding


@dataclass
class CapResult:
    regime: str
    cap_name: str | None
    cap_amount: float | None
    cap_range: dict | None
    member_cost_share_ytd: float
    over_cap: bool
    excess: float
    plan_year: int
    missing_inputs: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    disclosure_tier: int = 0
    finding_spec: dict | None = None

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "cap_name": self.cap_name,
            "cap_amount": self.cap_amount,
            "cap_range": self.cap_range,
            "member_cost_share_ytd": self.member_cost_share_ytd,
            "over_cap": self.over_cap,
            "excess": self.excess,
            "plan_year": self.plan_year,
            "missing_inputs": list(self.missing_inputs),
            "assumptions": list(self.assumptions),
            "confidence": self.confidence,
            "disclosure_tier": self.disclosure_tier,
            "disclosure_label": DISCLOSURE_TIER_LABELS[self.disclosure_tier],
            "finding_spec": self.finding_spec,
        }


def _plan_year(coverage: dict, as_of: date) -> tuple[int, bool]:
    """(plan_year, assumed). Uses coverage.plan_year / plan_effective_date year when
    captured; otherwise the calendar year of as_of, flagged assumed (DL: no plan-start
    month captured yet — same discipline as the accumulator)."""
    cov = coverage or {}
    if cov.get("plan_year"):
        try:
            return int(cov["plan_year"]), False
        except (ValueError, TypeError):
            pass
    eff = parse_iso_date(cov.get("plan_effective_date"))
    if eff is not None:
        return eff.year, False
    return as_of.year, True


def _cost_share_ytd(claims: list[dict], plan_year: int) -> float:
    """Sum the member's cost-share across claims in the plan year. Prefers the amount a
    claim applied to OOP, falling back to the member responsibility."""
    total = 0.0
    for entry in claims or []:
        eob = entry.get("eob", entry) if isinstance(entry, dict) else {}
        dt = parse_iso_date(eob.get("adjudication_date")) or parse_iso_date(eob.get("date_of_service"))
        if dt is not None and dt.year != plan_year:
            continue
        amt = as_float(eob.get("amount_applied_to_oop"))
        if amt is None:
            amt = as_float(eob.get("patient_responsibility"))
        if amt is not None:
            total += amt
    return round(total, 2)


def _over_cap_finding(regime: str, cap_name: str, cap: float, ytd: float, excess: float, plan_year: int) -> dict:
    return {
        "finding_type": "payer_side",
        "category": "cost_sharing_cap_exceeded",
        "subagent_source": "cap_engine",
        "voice_tier": "A",
        "facts": {
            "regime": regime,
            "cap_name": cap_name,
            "cap_amount": cap,
            "member_cost_share_ytd": ytd,
            "excess": excess,
            "plan_year": plan_year,
        },
        "recommendation": {
            "action": (
                f"The member's cost-share (${ytd:,.2f}) exceeds the {cap_name} cap "
                f"(${cap:,.2f}) — the ${excess:,.2f} above the cap should not be owed."
            ),
            "reasoning": (
                "Cost-sharing beyond the applicable cap is the member's, not the plan's, to "
                "recover — Tyndale flags the excess for dispute (Independent Audit Doctrine)."
            ),
        },
    }


def _fixed_cap_engine(
    regime: str, cap_name: str, claims: list[dict], coverage: dict, as_of: date
) -> CapResult:
    plan_year, assumed = _plan_year(coverage, as_of)
    ytd = _cost_share_ytd(claims, plan_year)
    assumptions: list[str] = []
    if assumed:
        assumptions.append(
            f"plan year assumed to be calendar year {plan_year}; plan-start month not captured"
        )
    try:
        const = lookup(regime, cap_name, plan_year)
    except CapConstantNotLoaded:
        assumptions.append(f"cap constants for {cap_name} ({plan_year}) not loaded — cap uncomputed")
        return CapResult(
            regime=regime, cap_name=cap_name, cap_amount=None, cap_range=None,
            member_cost_share_ytd=ytd, over_cap=False, excess=0.0, plan_year=plan_year,
            missing_inputs=[f"{cap_name}_{plan_year}"], assumptions=assumptions,
            confidence=0.2, disclosure_tier=2,
            finding_spec=missing_constant_finding(regime, cap_name, plan_year),
        )
    if not const.loaded:
        assumptions.append(f"{cap_name} value not yet loaded ({const.note})")
        return CapResult(
            regime=regime, cap_name=cap_name, cap_amount=None, cap_range=None,
            member_cost_share_ytd=ytd, over_cap=False, excess=0.0, plan_year=plan_year,
            missing_inputs=[cap_name], assumptions=assumptions, confidence=0.2,
            disclosure_tier=disclosure_tier(0, 1, missing_inputs=[cap_name]),
        )

    cap = const.amount
    excess = round(max(0.0, ytd - cap), 2)
    over = is_material(excess, cap, AUDIT_FLAG) and ytd > cap
    return CapResult(
        regime=regime, cap_name=cap_name, cap_amount=cap, cap_range=None,
        member_cost_share_ytd=ytd, over_cap=over, excess=excess if over else 0.0,
        plan_year=plan_year, assumptions=assumptions, confidence=0.7 if claims else 0.4,
        disclosure_tier=2 if over else 0,
        finding_spec=_over_cap_finding(regime, cap_name, cap, ytd, excess, plan_year) if over else None,
    )


def _medicaid_cap_engine(claims: list[dict], coverage: dict, as_of: date) -> CapResult:
    """Medicaid's 5%-of-household-income cost-share cap. Household income isn't collected
    (TODO(phil-decision): add the intake question), so the cap is RANGED over the income
    priors rather than dead-ended (Sprint C)."""
    plan_year, assumed = _plan_year(coverage, as_of)
    ytd = _cost_share_ytd(claims, plan_year)
    assumptions = ["Medicaid 5%-of-household-income cap; household income not collected — cap ranged over priors"]
    if assumed:
        assumptions.append(f"plan year assumed to be calendar year {plan_year}")
    const = lookup("medicaid", "household_cost_share_cap_pct", plan_year)  # loaded (0.05)
    pct = const.amount or 0.05
    income = as_float((coverage or {}).get("household_income"))

    if income is not None:
        cap = round(pct * income, 2)
        excess = round(max(0.0, ytd - cap), 2)
        over = is_material(excess, cap, AUDIT_FLAG) and ytd > cap
        return CapResult(
            regime="medicaid", cap_name="household_cost_share_cap_pct", cap_amount=cap,
            cap_range=None, member_cost_share_ytd=ytd, over_cap=over,
            excess=excess if over else 0.0, plan_year=plan_year, assumptions=assumptions,
            confidence=0.7, disclosure_tier=2 if over else 0,
            finding_spec=_over_cap_finding(
                "medicaid", "household_cost_share_cap_pct", cap, ytd, excess, plan_year
            ) if over else None,
        )

    prior = MISSING_DATA_PRIORS["household_income"]
    rng = compute_range(prior.plausible_values(), lambda inc: pct * inc, base_value=prior.base)
    return CapResult(
        regime="medicaid", cap_name="household_cost_share_cap_pct", cap_amount=rng.base,
        cap_range=rng.to_dict(), member_cost_share_ytd=ytd, over_cap=False, excess=0.0,
        plan_year=plan_year, missing_inputs=["household_income"], assumptions=assumptions,
        confidence=0.3,
        disclosure_tier=disclosure_tier(rng.width, rng.high, missing_inputs=["household_income"]),
    )


def _ma_moop_engine(claims: list[dict], coverage: dict, as_of: date) -> CapResult:
    """Medicare Advantage in-network MOOP. The plan-specific MOOP comes from coverage when
    captured; otherwise the (currently unloaded) CMS max — treated as a missing input."""
    plan_year, assumed = _plan_year(coverage, as_of)
    ytd = _cost_share_ytd(claims, plan_year)
    assumptions = []
    if assumed:
        assumptions.append(f"plan year assumed to be calendar year {plan_year}")
    moop = as_float((coverage or {}).get("oop_max_amount"))
    if moop is not None:
        excess = round(max(0.0, ytd - moop), 2)
        over = is_material(excess, moop, AUDIT_FLAG) and ytd > moop
        assumptions.append("MOOP read from the member's captured coverage")
        return CapResult(
            regime="medicare_advantage", cap_name="in_network_moop", cap_amount=moop,
            cap_range=None, member_cost_share_ytd=ytd, over_cap=over,
            excess=excess if over else 0.0, plan_year=plan_year, assumptions=assumptions,
            confidence=0.7, disclosure_tier=2 if over else 0,
            finding_spec=_over_cap_finding(
                "medicare_advantage", "in_network_moop", moop, ytd, excess, plan_year
            ) if over else None,
        )
    # Fall back to the registry constant (currently value-pending → missing input).
    return _fixed_cap_engine("medicare_advantage", "in_network_moop", claims, coverage, as_of)


# regime -> engine. Regimes without a constants-based cap (commercial uses the plan OOP-max
# via the accumulator; self_pay has none; dual_qmb is a $0-cost-share special case) return None.
def compute_cap(regime: str, claims: list[dict], coverage: dict | None, as_of: date) -> CapResult | None:
    coverage = coverage or {}
    if regime == "medicare_traditional":
        return _fixed_cap_engine("medicare_traditional", "part_d_oop_cap", claims, coverage, as_of)
    if regime == "tricare_va":
        return _fixed_cap_engine("tricare_va", "champva_catastrophic_cap", claims, coverage, as_of)
    if regime == "medicaid":
        return _medicaid_cap_engine(claims, coverage, as_of)
    if regime == "medicare_advantage":
        return _ma_moop_engine(claims, coverage, as_of)
    return None
