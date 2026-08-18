"""DRAFT — pending Brock sign-off (packet A6). Every Brock-owned X-rule constant, in ONE place.

The X2/X3/X5 checkers are parameterized entirely by this module, so Brock's amendments land as
a DATA change here — no checker logic moves. Sources: `docs/build-kit/37_x_rules_contracts_DRAFT.md`
(Cowork's drafts to X1's contract shape) and the engineering derivations noted per constant.
Stdlib-only, like every doctrine module, so tests and the e2e harness load it by file path.

What is Brock's in this file (his sign-off changes it):
  * X5_ERROR_TYPES — the 14-type taxonomy + the escape hatch and its sub-label rule.
  * X2_ACTION_MEANS / X2_INFORMATIONAL_MARKER — what counts as "an action".
  * X3_TIER_QUALIFIER — the disclosure-tier → qualifier-form mapping.
What is engineering's (seeds, replaced or ratified by him):
  * CATEGORY_TO_ERROR_TYPE / FINDING_TYPE_TO_ERROR_TYPE — the unambiguous derivations from
    the categories the engine already emits. Anything not listed uses the escape hatch with
    the category as its sub-label — never a guess promoted to a type.
  * INFORMATIONAL_CATEGORIES — engine states that are context, not billing errors.
  * X_KNOWN_GAPS — structural gaps that exist TODAY and are reported as notes rather than
    failures in the harness, so the contract can run before upstream fully feeds it. Each
    entry is a debt with a name; deleting one turns real enforcement on.
"""

from __future__ import annotations

# ── X5 · name-the-specific-error ─────────────────────────────────────────────────────────
# The proposed enum, verbatim from the draft (Brock: amend/rename/extend — this taxonomy is
# yours). `other_billing_error` is permitted ONLY with a named sub-label.
X5_ERROR_TYPES: frozenset[str] = frozenset(
    {
        "duplicate_charge",
        "upcoding",
        "unbundling",
        "units_exceeded",  # MUE
        "phantom_service",  # billed, didn't happen
        "balance_billing_violation",
        "deductible_misapplied",
        "cost_sharing_math_error",  # coinsurance/copay arithmetic
        "preventive_cost_shared",
        "noncovered_misapplied",  # covered service processed as not covered
        "extreme_markup",  # B4, uninsured/self-pay benchmark
        "cob_misordered",  # B6, wrong primary/secondary order
        "stale_accumulator",  # payer applied out-of-date deductible/OOP position
        "other_billing_error",  # escape hatch — sub-label REQUIRED
    }
)
X5_ESCAPE_HATCH = "other_billing_error"

# Typed reasons an impact may be legitimately unknown (silent absence still fails).
X5_IMPACT_UNKNOWN_REASONS: frozenset[str] = frozenset(
    {"awaiting_itemized_bill", "awaiting_eob", "awaiting_coverage_terms"}
)

# Engineering derivation: category → error_type, UNAMBIGUOUS mappings only. A category not
# here (e.g. cost_sharing_cap_exceeded, which could be math or a misapplied deductible) takes
# the escape hatch with the category as sub-label rather than a guess.
CATEGORY_TO_ERROR_TYPE: dict[str, str] = {
    "duplicate": "duplicate_charge",
    "upcoding": "upcoding",
    "upcoding_candidate": "upcoding",  # encounter-verification candidate of the same error
    "bundling": "unbundling",
    "balance_billing": "balance_billing_violation",
    "cost_sharing_miscalculation": "cost_sharing_math_error",
    "accumulator_discrepancy": "stale_accumulator",
    "non_covered": "noncovered_misapplied",
    "phantom_charge_candidate": "phantom_service",
    # Observed live in the first full dev sweep (2026-08-17): the pipeline emits the
    # confirmed-tier sibling of the candidate category. Same unambiguous target.
    "phantom_charge": "phantom_service",
}
# finding_type-level derivation, applied only when the category yields nothing.
FINDING_TYPE_TO_ERROR_TYPE: dict[str, str] = {
    "encounter_mismatch": "phantom_service",  # billed for something the user says didn't happen
}

# Engine states that are CONTEXT, not billing errors — X5 does not apply, and X2 accepts the
# informational typing for them. ("other" is deliberately absent: unknown is not informational.)
INFORMATIONAL_CATEGORIES: frozenset[str] = frozenset(
    {
        "out_of_scope",
        "regime_document_mismatch",
        "cap_constant_not_loaded",
        # Observed live in the first full dev sweep (2026-08-17) — the pipeline's all-clear /
        # audit-performed notes. Eng-classified as context (they assert the ABSENCE of an
        # error, so no action attaches and no error_type applies); Brock confirms via A6.
        "diagnostic_clear",
        "upcoding_diagnostic_clear",
        "diagnostic_audit_complete_no_confirmed_errors",
        "cost_sharing_audit",
    }
)

# The agents mint NOVEL all-clear phrasings every run (diagnostic_audit_clean,
# coverage_math_audit, … — 2026-08-18 sweep), so exact names can't keep up. These stems
# classify the FAMILY — but only for findings that CLAIM NO MONEY (an all-clear asserting a
# dollar gap is a contradiction the escape hatch logs instead of typing). Interim
# engineering rule pending Brock's A6 taxonomy, which supersedes this list.
INFORMATIONAL_CATEGORY_STEMS: tuple[str, ...] = ("_clear", "_clean", "_audit", "no_confirmed")


def category_matches_informational(category: str | None) -> bool:
    """Exact-set membership, else the stem families (see INFORMATIONAL_CATEGORY_STEMS)."""
    c = str(category or "")
    return c in INFORMATIONAL_CATEGORIES or any(s in c for s in INFORMATIONAL_CATEGORY_STEMS)

# ── X2 · surface-only-if-actionable ──────────────────────────────────────────────────────
# What counts as "an action" bound to a finding (draft: user-executable next step bound to
# THAT finding — a call step targeting it, a document request whose satisfaction advances it,
# a generated artifact, or an in-app confirm). In the current data model those all surface as
# one of these finding-level facts:
X2_ACTION_MEANS = (
    "recommendation.action",  # the scripted next step (feeds the gameplan call step)
    "facts.document_request",  # a document ask bound to this finding
)
# The explicit informational typing (draft: `presentation: informational_context`). Until
# upstream writes that field, a finding whose category is INFORMATIONAL_CATEGORIES counts as
# typed — that IS the current typing mechanism, and the draft's open question 2 (does §5.4's
# rung-0 reconciliation satisfy?) is answered "yes, as informational" pending Brock.
X2_INFORMATIONAL_MARKER = "presentation.informational_context"

# ── X3 · incomplete-input figures carry a naming qualifier ───────────────────────────────
# Disclosure tier → required qualifier form (draft, mirroring the locked disclosure ladder):
#   tier 0 → no qualifier PERMITTED (inputs complete; qualifying a complete figure hedges)
#   tier 1 → point form: the qualifier names the most material missing input
#   tier ≥2 → range form: {low}–{high} until the named input arrives
X3_TIER_QUALIFIER: dict[int, str] = {0: "none", 1: "point", 2: "range", 3: "range"}
# "Estimated" alone fails — generic words that do NOT satisfy the naming requirement:
X3_GENERIC_QUALIFIERS: frozenset[str] = frozenset(
    {"estimated", "estimate", "approximate", "approximately", "about", "roughly"}
)

# ── Known structural gaps (engineering debt ledger — NOT Brock's) ────────────────────────
# Reported by the harness as notes instead of failures, each with the reason it exists. The
# contract tests assert the checkers CATCH these shapes; the harness allowlists them until
# upstream feeds the data. Delete an entry to turn enforcement on.
X_KNOWN_GAPS: dict[str, str] = {
    "x5:no_line_item_ref": (
        "most findings do not yet carry line-item refs — only encounter-mismatch findings "
        "write facts.line_item_id; agent findings need the refs plumbed through"
    ),
    # x3:no_qualifier_surface DELETED 2026-08-18 — the rung-2 completion put the qualifier on
    # the three-number moment (same visual unit, point/range by tier). Enforcement is ON.
    "x5:impact_missing_untyped": (
        "real error findings (phantom_charge, upcoding_candidate — first full dev sweep, "
        "2026-08-17) carry neither facts.impact nor a typed impact_unknown_reason: the agents "
        "do not emit the X5_IMPACT_UNKNOWN_REASONS vocabulary yet"
    ),
    "x2:no_attached_action+not_typed_informational": (
        "error findings can reach the user without a bound action (phantom_charge, first full "
        "dev sweep 2026-08-17) — the finding->gameplan action binding is not yet guaranteed "
        "by the pipeline"
    ),
    "scenario:balance_billing_nsa_seed": (
        "the balance-billing finding activates with the 50-state NSA seed (DL-81/DL-88 — "
        "Brock's launch condition; enable_nsa_checks stays OFF per Phil 2026-08-18). The "
        "balance_billing_mismatch scenario asserts the GATED behavior until the seed lands — "
        "this entry keeps the gap visible instead of buried in a green row"
    ),
}
