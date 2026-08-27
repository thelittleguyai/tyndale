"""Attribution drives the action surface (audit 2026-08-27 item 2): a finding's derived
responsible_party — the value a matched payer-side rule carries — routes who to call, which
identifier to quote, and which opener renders. First direct coverage of
grounding.derive_responsible_party (previously zero)."""

from types import SimpleNamespace

from app.agents.grounding import derive_responsible_party
from app.sources.call_identifiers import CallIdentifiers
from app.sources.gameplan import build_gameplan


def _finding(finding_type="provider_side", facts=None, category="cost_sharing_miscalculation"):
    return SimpleNamespace(
        finding_id="f-1",
        finding_type=finding_type,
        category=category,
        facts=facts or {},
        legal_claim=None,
        recommendation={"action": "Call and dispute the charge."},
    )


# ── derive_responsible_party: explicit wins, invalid falls back ─────────────────────
def test_explicit_valid_attribution_wins_over_finding_type():
    f = _finding(finding_type="provider_side", facts={"responsible_party": "payer"})
    assert derive_responsible_party(f) == "payer"


def test_invalid_explicit_value_falls_back_to_the_type_map():
    f = _finding(finding_type="payer_side", facts={"responsible_party": "the government"})
    assert derive_responsible_party(f) == "payer"
    f = _finding(finding_type="provider_side", facts={"responsible_party": 42})
    assert derive_responsible_party(f) == "provider"


def test_unknown_type_without_explicit_is_either():
    assert derive_responsible_party(_finding(finding_type="informational")) == "either"


def test_encounter_mismatch_maps_to_either_then_routes_provider_in_gameplan():
    f = _finding(finding_type="encounter_mismatch")
    assert derive_responsible_party(f) == "either"


# ── the action surface: a payer-attributed finding is a payer call with a claim# ────
_IDS = CallIdentifiers(
    claim_number="CLM-123", account_number="ACCT-9", provider_phone="555-1111",
    payer_phone="555-2222",
)


def test_payer_attributed_finding_builds_a_payer_step_with_claim_number():
    # provider_side TYPE but payer attribution (the schema-extension case): the step must
    # go to the insurer with the CLAIM number — not the provider's billing office.
    f = _finding(finding_type="provider_side", facts={"responsible_party": "payer"})
    steps = build_gameplan([f], identifiers=_IDS)
    assert steps and steps[0].party == "payer"
    assert steps[0].party_label == "your insurance company"
    assert steps[0].responsible_party == "payer"
    assert steps[0].reference_kind == "claim" and steps[0].reference_number == "CLM-123"
    assert steps[0].phone == "555-2222"


def test_either_keeps_type_routing_and_says_so():
    f = _finding(finding_type="encounter_mismatch")
    steps = build_gameplan([f], identifiers=_IDS)
    assert steps[0].party == "provider"  # type-map fallback routing
    assert steps[0].responsible_party == "either"  # carried for the client/script
    assert steps[0].reference_kind == "account" and steps[0].reference_number == "ACCT-9"


def test_no_attribution_matches_legacy_type_routing():
    f = _finding(finding_type="payer_side")
    steps = build_gameplan([f], identifiers=_IDS)
    assert steps[0].party == "payer" and steps[0].responsible_party == "payer"
