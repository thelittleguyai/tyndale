"""X2/X3/X5 doctrine contracts — the CI teeth (implemented from 37_x_rules_contracts_DRAFT.md).

Same discipline as test_x1_contract.py: the checkers load by file path from
intelligence-layer/evals/doctrine, every Brock-owned constant lives in doctrine_config
(DRAFT pending packet A6 — his amendments are a data change), and each contract's canonical
worked failing example from the draft is asserted BY NAME. The teeth run both directions:
the failure shapes are caught, the healthy shapes pass, and the derivation the product uses
is literally the checker's own function, so they can't disagree.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


_DOCTRINE = pathlib.Path(__file__).resolve().parents[2] / "intelligence-layer" / "evals" / "doctrine"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _DOCTRINE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cfg = _load("doctrine_config")
x2 = _load("x2_finding_action")
x3 = _load("x3_missing_input_qualifier")
x5 = _load("x5_error_finding_shape")


def _finding(**kw) -> dict:
    base = {
        "finding_id": "f-1", "finding_type": "payer_side",
        "category": "cost_sharing_miscalculation", "facts": {"gap": 640.0},
        "recommendation": {"action": "Call your insurer to dispute the math."},
    }
    base.update(kw)
    return base


# ── X2 ───────────────────────────────────────────────────────────────────────────────────
def test_x2_canonical_failure_named():
    """The draft's worked example: a finding with no action and no informational typing."""
    f = _finding(category="deductible_order", recommendation=None, facts={"gap": 10.0})
    v = x2.check_x2([f])
    assert not v.passed
    assert "no_attached_action+not_typed_informational" in v.reasons[0]


def test_x2_action_or_informational_passes():
    assert x2.check_x2([_finding()]).passed  # recommendation.action
    assert x2.check_x2([_finding(recommendation=None, facts={"document_request": "eob"})]).passed
    v = x2.check_x2([_finding(category="out_of_scope", recommendation=None, facts={})])
    assert v.passed and any("informational_context" in n for n in v.notes)
    # The explicit typing wins even on an otherwise-unknown category (draft question 2).
    assert x2.check_x2(
        [_finding(category="reconciliation", recommendation=None, presentation="informational_context", facts={})]
    ).passed


def test_x2_page_level_actions_do_not_rescue_a_bare_finding():
    """finding→action binding, not page→actions: one actionable sibling can't cover another
    finding's bareness."""
    bare = _finding(finding_id="f-2", category="mystery", recommendation=None, facts={"gap": 5.0})
    v = x2.check_x2([_finding(), bare])
    assert not v.passed and len(v.reasons) == 1


def test_x2_vacuous_pass_is_noted():
    v = x2.check_x2([])
    assert v.passed and "no_findings (vacuous pass)" in v.notes


# ── X3 ───────────────────────────────────────────────────────────────────────────────────
def _figure(**kw) -> dict:
    base = {
        "label": "What you should owe", "value": 612.40,
        "missing_inputs": ["sbc"], "tier": 1,
        "qualifier": {"text": "without your SBC this is my best number",
                      "names": ["sbc"], "same_unit": True, "form": "point"},
    }
    base.update(kw)
    return base


def test_x3_canonical_failure_named():
    """The draft's worked example: a bare figure while the SBC is missing."""
    v = x3.check_x3([_figure(qualifier=None)])
    assert not v.passed
    assert any("no_qualifier_in_unit" in r for r in v.reasons)
    assert any("missing_inputs_nonempty(sbc)" in n for n in v.notes)


def test_x3_generic_estimated_fails_but_a_naming_qualifier_passes():
    generic = _figure(qualifier={"text": "estimated", "names": ["estimated"], "same_unit": True, "form": "point"})
    v = x3.check_x3([generic])
    assert not v.passed and any("generic_qualifier" in r for r in v.reasons)
    assert x3.check_x3([_figure()]).passed


def test_x3_detached_qualifier_fails():
    detached = _figure(qualifier={"text": "without your SBC…", "names": ["sbc"], "same_unit": False, "form": "point"})
    v = x3.check_x3([detached])
    assert not v.passed and any("qualifier_detached" in r for r in v.reasons)


def test_x3_tier_two_requires_the_range_form():
    point_at_tier2 = _figure(tier=2)
    v = x3.check_x3([point_at_tier2])
    assert not v.passed and any("tier_2_requires_range_form" in r for r in v.reasons)
    ranged = _figure(tier=2, qualifier={"text": "between $520 and $710 until I see your SBC",
                                        "names": ["sbc"], "same_unit": True, "form": "range"})
    assert x3.check_x3([ranged]).passed


def test_x3_tier_zero_forbids_hedging_a_complete_figure():
    complete = _figure(missing_inputs=[], tier=0)
    v = x3.check_x3([complete])
    assert not v.passed and any("qualifier_on_complete_figure" in r for r in v.reasons)
    assert x3.check_x3([_figure(missing_inputs=[], tier=0, qualifier=None)]).passed


# ── X5 ───────────────────────────────────────────────────────────────────────────────────
def test_x5_canonical_failure_named():
    """The draft's worked example: vague, untyped, unreferenced, unquantified."""
    vague = {
        "finding_id": "f-9", "finding_type": "provider_side", "category": "something_odd",
        "facts": {"gap": 50.0}, "recommendation": {"action": "ask your provider"},
    }
    v = x5.check_x5([vague])
    assert not v.passed
    joined = " | ".join(v.reasons)
    # escape hatch WITH sub-label satisfies the enum leg; refs + impact behave per contract
    assert "no_line_item_ref" in joined
    assert "escape_hatch" in " | ".join(v.notes)  # sub-label = the category, honest not guessed


def test_x5_unambiguous_category_derivation():
    """The product-side annotation and the checker share ONE derivation function."""
    et, sub = x5.derive_error_type(_finding(category="duplicate"))
    assert (et, sub) == ("duplicate_charge", None)
    et, _ = x5.derive_error_type(_finding(category="accumulator_discrepancy"))
    assert et == "stale_accumulator"
    et, _ = x5.derive_error_type({"category": "verified_ok", "finding_type": "encounter_mismatch"})
    assert et == "phantom_service"  # finding_type-level fallback
    et, sub = x5.derive_error_type(_finding(category="cost_sharing_cap_exceeded"))
    assert et == cfg.X5_ESCAPE_HATCH and sub == "cost_sharing_cap_exceeded"  # ambiguous → hatch
    assert x5.derive_error_type(_finding(category="out_of_scope")) == (None, None)  # informational


def test_x5_healthy_error_finding_passes():
    good = _finding(
        category="cost_sharing_miscalculation",
        facts={"gap": 640.0, "line_item_id": "li-1"},
    )
    v = x5.check_x5([good])
    assert v.passed and v.errors_checked == 1


def test_x5_typed_impact_unknown_passes_but_silent_absence_fails():
    typed = _finding(facts={"line_item_id": "li-1", "impact_unknown_reason": "awaiting_eob"})
    v = x5.check_x5([typed])
    assert v.passed and any("impact_unknown(awaiting_eob)" in n for n in v.notes)
    silent = _finding(facts={"line_item_id": "li-1"})
    v = x5.check_x5([silent])
    assert not v.passed and any("impact_missing_untyped" in r for r in v.reasons)


def test_x5_escape_hatch_requires_a_sub_label():
    hatched = _finding(category="x", error_type=cfg.X5_ESCAPE_HATCH,
                       facts={"gap": 5.0, "line_item_id": "li-1"})
    v = x5.check_x5([hatched])
    assert not v.passed and any("escape_hatch_without_sub_label" in r for r in v.reasons)


def test_x5_free_text_error_type_is_rejected():
    """Never free text — an unenumerated type fails even though it LOOKS specific."""
    freetext = _finding(error_type="weird_charge", facts={"gap": 5.0, "line_item_id": "li-1"})
    v = x5.check_x5([freetext])
    assert not v.passed and any("error_type_missing_or_unenum" in r for r in v.reasons)


def test_x5_informational_findings_are_out_of_scope():
    v = x5.check_x5([_finding(category="regime_document_mismatch", facts={})])
    assert v.passed and "no_error_findings (vacuous pass)" in v.notes


# ── the product-side annotation seam ─────────────────────────────────────────────────────
def test_runtime_annotates_findings_with_the_same_derivation():
    """FindingOut leaves the read seam carrying the derived type + honest provenance."""
    from app.agents.orchestrator import _with_source_line
    from app.schemas.case_file import FindingOut

    f = FindingOut(
        finding_id="f-1", finding_type="payer_side", category="cost_sharing_miscalculation",
        subagent_source="math_person", voice_tier="B", facts={"gap": 640.0},
    )
    out = _with_source_line(f)
    assert out.error_type == "cost_sharing_math_error"
    assert out.error_type_source == "derived_draft"  # never mistaken for upstream-asserted

    hatched = _with_source_line(FindingOut(
        finding_id="f-2", finding_type="payer_side", category="cost_sharing_cap_exceeded",
        subagent_source="math_person", voice_tier="B", facts={"gap": 10.0},
    ))
    assert hatched.error_type == cfg.X5_ESCAPE_HATCH
    assert hatched.error_type_sub_label == "cost_sharing_cap_exceeded"

    info = _with_source_line(FindingOut(
        finding_id="f-3", finding_type="payer_side", category="out_of_scope",
        subagent_source="lead_planner", voice_tier="A", facts={},
    ))
    assert info.error_type is None  # informational — X5 does not apply


def test_config_is_coherent():
    """Guards the config itself: every mapped target is in the enum, the hatch is in the
    enum, and the known-gap keys point at real reason prefixes."""
    assert cfg.X5_ESCAPE_HATCH in cfg.X5_ERROR_TYPES
    for target in {**cfg.CATEGORY_TO_ERROR_TYPE, **{"": ""}}.values():
        if target:
            assert target in cfg.X5_ERROR_TYPES, target
    for target in cfg.FINDING_TYPE_TO_ERROR_TYPE.values():
        assert target in cfg.X5_ERROR_TYPES
    for key in cfg.X_KNOWN_GAPS:
        rule, reason = key.split(":", 1)
        # "scenario:" (2026-08-18): a deliberately-gated scenario names its ledger entry so
        # the harness prints the gap on every run (balance-billing awaits the NSA seed).
        assert rule in ("x2", "x3", "x5", "scenario") and len(reason) > 3
    assert len(cfg.X5_ERROR_TYPES) == 14


# ── the informational-stem interim (2026-08-18, pending A6) ───────────────────────────────
def test_stems_classify_novel_all_clear_phrasings_but_never_mapped_error_categories():
    """The agents mint new all-clear names every run (diagnostic_audit_clean,
    coverage_math_audit); the stems catch the family. COHERENCE: no category mapped to a
    real error_type may ever stem-match informational — that would silently erase errors."""
    assert cfg.category_matches_informational("diagnostic_audit_clean")
    assert cfg.category_matches_informational("coverage_math_audit")
    assert cfg.category_matches_informational("three_number_audit")
    assert cfg.category_matches_informational("out_of_scope")  # exact set still works
    assert not cfg.category_matches_informational("balance_billing")
    assert not cfg.category_matches_informational("phantom_charge")
    for mapped in cfg.CATEGORY_TO_ERROR_TYPE:
        assert not cfg.category_matches_informational(mapped), (
            f"error category {mapped!r} stem-matches informational — errors would vanish"
        )


def test_annotate_stamps_informational_only_when_no_money_is_claimed():
    """The read-seam stamp: an all-clear family finding with no dollar claim becomes
    presentation=informational_context (X2/X5 then exclude it); the SAME category claiming
    money is the logged escape hatch and stays an error. Explicit upstream presentation is
    never overwritten."""
    from types import SimpleNamespace

    from app.sources.error_types import annotate_error_type

    def finding(category, facts=None, presentation=None):
        return SimpleNamespace(
            category=category, facts=facts or {}, presentation=presentation,
            error_type=None, error_type_sub_label=None, finding_type="payer_side",
        )

    clean = annotate_error_type(finding("diagnostic_audit_clean"))
    assert clean.presentation == "informational_context"
    assert clean.error_type is None  # X5 does not apply to informational context

    moneyed = annotate_error_type(finding("coverage_math_audit", facts={"gap": 250.0}))
    assert moneyed.presentation is None  # escape hatch: logged, never silently typed
    assert moneyed.error_type is not None  # still an error (the hatch at minimum)

    explicit = annotate_error_type(finding("diagnostic_clear", presentation="upstream_set"))
    assert explicit.presentation == "upstream_set"  # upstream typing is never overwritten
