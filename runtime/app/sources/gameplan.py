"""The sub-case gameplan (D5, Phase C §2 — DL-91).

A gameplan is the ordered set of phone calls the user makes to pursue what the audit found —
biggest-dollar item first, so the user's first call is the one that matters most. Engineering
renders the STRUCTURE here (which party to call, in what order, the four per-call beats, the
finding-specific problem/ask); the connective SCAFFOLDING copy — how to open the call, how to
get it in writing, what to say if they push back — is Brock's authored orchestration-script copy
(D1), interpolated by key. We never invent legal or coverage language: the "problem" beat is the
finding's own Tier-B claim and the "ask" is its Tier-C recommendation, both agent-authored.

Data honesty (§4): a step's ``dollar_impact`` is the finding's ESTIMATED gap (facts['gap']) — a
potential, never a confirmed recovery — and is labeled as such in the view. A finding with no
recommended action produces no step (it still appears in the findings list).
"""

from __future__ import annotations

from app.agents.context_loader import orchestration_step
from app.db.models.findings import Finding
from app.schemas.case_summary import CallScript, GameplanStep

# finding_type -> (party token, plain-language who-to-call). encounter_mismatch is a provider
# billing error (charged for something that didn't happen), so it routes to the provider too.
_PARTY: dict[str, tuple[str, str]] = {
    "payer_side": ("payer", "your insurance company"),
    "provider_side": ("provider", "the provider's billing office"),
    "encounter_mismatch": ("provider", "the provider's billing office"),
}

# Humanized step titles for the categories the audit emits; unknown categories title-case cleanly.
_CATEGORY_TITLE: dict[str, str] = {
    "cost_sharing_miscalculation": "Fix the cost-sharing math",
    "accumulator_discrepancy": "Correct your deductible/out-of-pocket tally",
    "bundling": "Challenge the unbundled charges",
    "upcoding": "Dispute the service level billed",
    "duplicate": "Remove the duplicate charge",
    "balance_billing": "Stop the balance bill",
    "non_covered": "Recheck the coverage denial",
}


def humanize_category(category: str) -> str:
    return _CATEGORY_TITLE.get(category, category.replace("_", " ").capitalize())


def _dollar_of(f: Finding) -> float | None:
    gap = (f.facts or {}).get("gap")
    if gap is None:
        return None
    try:
        return round(max(0.0, float(gap)), 2)
    except (TypeError, ValueError):
        return None


def _action_of(f: Finding) -> str | None:
    rec = f.recommendation or {}
    action = rec.get("action")
    return action.strip() if isinstance(action, str) and action.strip() else None


def _problem_of(f: Finding) -> str:
    """The 'here's the problem' beat: the finding's own Tier-B claim, else the Tier-C reasoning.
    Agent-authored — engineering never composes legal/coverage language here."""
    claim = (f.legal_claim or {}).get("claim")
    if isinstance(claim, str) and claim.strip():
        return claim.strip()
    reasoning = (f.recommendation or {}).get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return humanize_category(f.category)


def build_gameplan(findings: list[Finding]) -> list[GameplanStep]:
    """Actionable findings (those with a recommended action), ordered biggest-dollar-first, each
    rendered as a per-call script. Findings without an action are omitted (they stay in the
    findings list); ties and missing dollars sort last but keep a stable order."""
    actionable = [f for f in findings if _action_of(f) is not None]
    actionable.sort(key=lambda f: (_dollar_of(f) or 0.0), reverse=True)

    steps: list[GameplanStep] = []
    for i, f in enumerate(actionable, start=1):
        party, party_label = _PARTY.get(f.finding_type, ("provider", "the provider's billing office"))
        opener_key = "call_script_opener_payer" if party == "payer" else "call_script_opener_provider"
        steps.append(
            GameplanStep(
                index=i,
                finding_id=str(f.finding_id),
                title=humanize_category(f.category),
                party=party,
                party_label=party_label,
                dollar_impact=_dollar_of(f),
                script=CallScript(
                    when_they_pick_up=orchestration_step(opener_key, party=party_label),
                    the_problem=_problem_of(f),
                    the_ask=_action_of(f) or "",
                    get_it_in_writing=orchestration_step("call_script_get_it_in_writing"),
                    if_they_push_back=[orchestration_step("call_script_if_they_push_back")],
                ),
            )
        )
    return steps
