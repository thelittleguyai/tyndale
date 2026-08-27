"""error_detection_rules payload contract (Brock's 38 §3 extension, 2026-08-22).

The JSON Schema in intelligence-layer/collections/schemas/error_detection_rules.json is the
authoring surface (seed_fixtures.py validates against it). This module is the PROGRAMMATIC
mirror for ingestion paths and tests: same enums, same conditional rule, named reasons.
The sync test in tests/test_rule_schema_extension.py holds the two together.
"""

from __future__ import annotations

RULE_CLASSES = ("provider_coding", "payer_adjudication", "legal_protection", "pricing")
RESPONSIBLE_PARTIES = ("provider", "payer", "either")
PROVIDER_CODING_RULE_TYPES = (
    "ncci_ptp", "mue", "modifier_validity", "upcoding_pattern",
    "phantom_charge",
)
# The 2026-08-22 payer-side extension — adjudication errors, not code conflicts.
# aca_preventive moved here 2026-08-27 (audit item 6): the ACA preventive rules are
# legal_protection / payer-attributed cost-sharing errors (the fixture backfill already
# says so) — they were misfiled under provider coding. NOTE: the full
# RULE_TYPE_TO_ERROR_TYPE map stays unbuilt pending Brock's sign-off; this fixes only
# the misfile.
PAYER_SIDE_RULE_TYPES = (
    "aca_preventive",
    "deductible_misapplication",
    "oop_max_ignored",
    "network_status_misapplied",
    "coinsurance_rate_error",
    "auth_on_file_ignored",
    "allowed_amount_above_contract",
    "cob_misordering",
)
RULE_TYPES = PROVIDER_CODING_RULE_TYPES + PAYER_SIDE_RULE_TYPES

_REQUIRED = (
    "rule_id", "rule_type", "rule_class", "responsible_party",
    "effective_date_start", "authority", "narrative_text",
)


def validate_error_detection_rule(payload: dict) -> list[str]:
    """Named reasons the payload violates the contract; [] when it conforms.

    The load-bearing conditional, enforced BOTH directions: rule_class=provider_coding
    REQUIRES applicable_codes (a coding rule with no codes matches nothing honestly);
    every other class MAY carry codes but never has to (payer-side rules match on
    adjudication facts — EOB math, network status, accumulator positions)."""
    reasons: list[str] = []
    for key in _REQUIRED:
        if not payload.get(key):
            reasons.append(f"missing_required:{key}")
    rc = payload.get("rule_class")
    if rc is not None and rc not in RULE_CLASSES:
        reasons.append(f"unknown_rule_class:{rc}")
    rt = payload.get("rule_type")
    if rt is not None and rt not in RULE_TYPES:
        reasons.append(f"unknown_rule_type:{rt}")
    rp = payload.get("responsible_party")
    if rp is not None and rp not in RESPONSIBLE_PARTIES:
        reasons.append(f"unknown_responsible_party:{rp}")
    codes = payload.get("applicable_codes")
    if rc == "provider_coding" and not codes:
        reasons.append("provider_coding_requires_applicable_codes")
    if codes is not None and (
        not isinstance(codes, list) or not all(isinstance(c, str) and c for c in codes)
    ):
        reasons.append("applicable_codes_must_be_string_list")
    if "effective_date_end" not in payload:
        reasons.append("missing_required:effective_date_end")  # null allowed, absence not
    return reasons
