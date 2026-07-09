"""Canonical plan-type / coverage-regime vocabulary — the SINGLE SOURCE OF TRUTH (Brock memo
2026-07-06, approved 14-value enum; supersedes the shipped 7-value set).

This one definition is consumed by:
  * the runtime coverage-regime detection + CHECK constraints (this repo),
  * ``packages/shared/src/intake.ts`` (mirror — kept in sync by test),
  * the ``laws_regulations.json`` schema's ``scope.plan_types_bound`` (mirror — kept in sync by
    ``tests/test_plan_types_canonical.py``, which reads the schema and asserts equality).

``plan_types_bound`` (which populations a law binds) and ``coverage_regime`` (what a case's
coverage IS) share this vocabulary. ``all`` is a SCHEMA-ONLY wildcard for a law that binds every
population; it is never a detected regime.
"""

from __future__ import annotations

# The 14 canonical plan types. Order is authoritative (used by the drift tests + fixtures).
PLAN_TYPES: tuple[str, ...] = (
    # Fully-insured commercial regulated by state DOI — state surprise-billing/appeal law binds.
    "state_regulated_commercial",
    # Self-funded ERISA employer plan — state insurance law does NOT bind (29 U.S.C. 1144
    # preemption); federal (NSA/ERISA/45 CFR 147.136) does. Rarely detectable from a card.
    "erisa_self_funded",
    # Original/traditional Medicare (Parts A/B), incl. Medigap supplement.
    "medicare_traditional",
    # Medicare Advantage (Part C) — a private plan administering Medicare benefits.
    "medicare_advantage",
    # Medicaid fee-for-service — the state pays providers directly.
    "medicaid_ffs",
    # Medicaid managed care — a private MCO (Molina/Centene/etc.) administers Medicaid benefits.
    "medicaid_mco",
    # Dually eligible for Medicare + Medicaid. qmb_status attribute gates the QMB never-bill check.
    "dual_eligible",
    # Uninsured / paying out of pocket — GFE / PPDR (No Surprises Act §2799B) rights apply.
    "self_pay",
    # TRICARE (active/retired military + families).
    "tricare",
    # VA health care + CHAMPVA (veterans / their dependents).
    "va_champva",
    # FEHB / PSHB (federal + postal employees). FEHBA preempts state insurance law
    # (5 U.S.C. 8902(m)(1)); balance-billing handled via the OPM contract (8902(p)); appeals under
    # 5 CFR 890.105/.107. NOT ERISA, NOT state — a STATE-LAW entry must NEVER bind this value.
    "fehb_pshb",
    # Self-funded state/county/city/school ("non-federal governmental") plan — non-ERISA
    # (29 U.S.C. 1003(b)(1)); appeals cite 45 CFR 147.136; the NSA is NOT opt-out-able for it.
    # (A FULLY-INSURED governmental plan is state_regulated_commercial + governmental_fully_insured.)
    "nonfederal_governmental",
    # Short-term limited-duration insurance — excluded from "individual coverage" (45 CFR 144.103):
    # no NSA, no ACA appeals. Its duration threshold is a state-dependent, re-verifiable constant
    # (see plan_constants.STLDI_MAX_DURATION), never hardcoded.
    "stldi",
    # Excepted benefits (HCSMs, fixed-indemnity, Farm Bureau plans): not insurance. Its rule-set
    # INHERITS self_pay (GFE/PPDR rights) plus a pursue-reimbursement step (see EXCEPTED_INHERITS).
    "excepted_coverage",
)

# The schema also accepts 'all' — a law that binds every population. NOT a detected regime.
SCHEMA_WILDCARD = "all"
PLAN_TYPES_WITH_ALL: tuple[str, ...] = (*PLAN_TYPES, SCHEMA_WILDCARD)

_PLAN_TYPE_SET = frozenset(PLAN_TYPES)

# Commercial-family regimes: the audit's generic baseline rules ARE commercial, so these carry no
# "population corpus pending" assumption (everything else does — Sprint B / DL-82).
COMMERCIAL_FAMILY: frozenset[str] = frozenset(
    {"state_regulated_commercial", "erisa_self_funded"}
)

# Regimes where federal surprise-billing (NSA) + ACA internal/external appeal rights DO NOT apply —
# claiming them would be a wrong answer (why Brock split these out). The audit router must SUPPRESS
# NSA/ACA-appeal claims for these, not just tag an assumption.
SUPPRESS_FEDERAL_PROTECTIONS: frozenset[str] = frozenset({"stldi", "excepted_coverage"})

# Rule-set inheritance: excepted_coverage runs the self_pay rule-set (GFE/PPDR) + a
# pursue-reimbursement step. Encoded as an explicit mapping (regime -> inherited rule-set base),
# consumed by the regime->ruleset router — never a copy of the rules.
RULESET_INHERITS: dict[str, str] = {"excepted_coverage": "self_pay"}

# Coverage attributes (typed keys) and the regimes each is valid on. None == valid on any regime.
# The QMB flagship check keys on qmb_status == True (and MUST NOT fire when null/false).
ATTRIBUTE_REGIME_COMPAT: dict[str, frozenset[str] | None] = {
    "qmb_status": frozenset({"dual_eligible"}),
    "ihs_prc_eligible": None,  # Indian Health Service / Purchased & Referred Care — any regime
    "grandfathered": None,  # a grandfathered plan can be commercial or governmental
    "market_segment": None,  # individual | small_group | large_group — informational
    "church_plan": None,  # ERISA-exempt church plan — can accompany several regimes
    "medigap": frozenset({"medicare_traditional"}),
    "dsnp": frozenset({"medicare_advantage"}),  # D-SNP is an MA product
    "governmental_fully_insured": frozenset({"state_regulated_commercial"}),
}
ATTRIBUTE_KEYS: frozenset[str] = frozenset(ATTRIBUTE_REGIME_COMPAT)


def is_plan_type(value: str | None) -> bool:
    """True if ``value`` is one of the 14 canonical plan types (NOT the 'all' wildcard)."""
    return value in _PLAN_TYPE_SET


def attributes_incompatible(regime: str | None, attributes: dict | None) -> list[str]:
    """Return the attribute keys present on ``attributes`` that are NOT valid for ``regime``
    (unknown keys are also reported). Empty list == compatible. Pure + deterministic."""
    problems: list[str] = []
    for key, val in (attributes or {}).items():
        if val is None:
            continue  # a null attribute is 'unknown' — never a compatibility error
        allowed = ATTRIBUTE_REGIME_COMPAT.get(key, "unknown")
        if allowed == "unknown":
            problems.append(f"unknown attribute '{key}'")
        elif allowed is not None and regime not in allowed:
            problems.append(f"attribute '{key}' is not valid on regime '{regime}'")
    return problems
