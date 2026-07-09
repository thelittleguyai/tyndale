"""Coverage-regime detection engine (Sprint B, DL-82) — table-driven cases per regime,
plus ambiguity and the MBI validator. The classifier is pure; detection is never
guessed, so thin/conflicting evidence must resolve to ambiguous (regime=None)."""

from __future__ import annotations

import pytest

from app.sources.regime_detection import (
    REGIMES,
    detect_regime,
    is_valid_mbi,
    is_valid_regime,
    signals_from_fields,
)


@pytest.mark.parametrize(
    "raw,ok",
    [
        ("1EG4-TE5-MK73", True),  # canonical CMS example MBI
        ("1EG4TE5MK73", True),  # separators are cosmetic
        ("123-45-6789", False),  # SSN shape, not an MBI
        ("0EG4TE5MK73", False),  # position 1 may not be 0
        ("1SG4TE5MK73", False),  # 'S' is an excluded MBI letter
        ("", False),
        (None, False),
    ],
)
def test_mbi_validator(raw, ok):
    assert is_valid_mbi(raw) is ok


# (coverage fields, document types) -> expected regime + minimum confidence. 14-value vocabulary
# (Brock 2026-07-06), one case per signal.
_CASES = [
    ("medicare_traditional_msn", {"member_id": "1EG4TE5MK73"}, ["msn"], "medicare_traditional", "high"),
    ("medicare_traditional_mbi", {"member_id": "1EG4TE5MK73"}, [], "medicare_traditional", "medium"),
    ("ma_branding", {"payer_name": "UnitedHealthcare", "plan_name": "Medicare Advantage Complete"}, [], "medicare_advantage", "medium"),
    ("ma_eob_doc", {"payer_name": "Humana", "plan_name": "Gold Plus"}, ["ma_eob"], "medicare_advantage", "high"),
    # medicaid split: state-plan branding → FFS; an MCO brand / mco_notice → MCO.
    ("medicaid_ffs_branding", {"payer_name": "MassHealth"}, [], "medicaid_ffs", "medium"),
    ("medicaid_mco_brand", {"payer_name": "Molina Healthcare", "plan_name": "Medicaid"}, ["mco_notice"], "medicaid_mco", "high"),
    ("dual", {"member_id": "1EG4TE5MK73", "payer_name": "Medicaid Managed Care"}, [], "dual_eligible", "medium"),
    # tricare/va split.
    ("tricare", {"payer_name": "TRICARE East (Humana Military)"}, [], "tricare", "medium"),
    ("va_statement", {"payer_name": "Department of Veterans Affairs"}, ["va_statement"], "va_champva", "high"),
    ("state_regulated_commercial", {"payer_name": "Aetna", "plan_name": "PPO", "group_number": "G1", "rx_bin": "610502"}, [], "state_regulated_commercial", "high"),
    # --- new v2 regimes (one per signal) ---
    ("fehb", {"plan_name": "FEHB Blue Cross Standard Option"}, [], "fehb_pshb", "high"),
    ("nonfederal_governmental", {"payer_name": "Anthem", "group_number": "G", "rx_bin": "6", "employer_name": "County of Alameda"}, [], "nonfederal_governmental", "medium"),
]


@pytest.mark.parametrize("name,coverage,docs,expected,min_conf", _CASES, ids=[c[0] for c in _CASES])
def test_regime_cases(name, coverage, docs, expected, min_conf):
    d = detect_regime(signals_from_fields(coverage, docs))
    assert d.regime == expected, f"{name}: {d.evidence}"
    order = {"low": 0, "medium": 1, "high": 2}
    assert order[d.confidence] >= order[min_conf], f"{name}: confidence {d.confidence} < {min_conf}"
    assert d.regime in REGIMES
    assert d.evidence  # every positive detection explains itself
    assert d.verified is False  # detection alone never sets verified; the ladder does


def test_stldi_notice_is_highest_signal():
    # The mandated first-page STLDI notice overrides commercial-looking branding.
    d = detect_regime(
        signals_from_fields(
            {"payer_name": "UnitedHealthcare", "group_number": "G1"},
            [],
            document_text_blobs=["Important: THIS IS NOT QUALIFYING HEALTH COVERAGE under the ACA."],
        )
    )
    assert d.regime == "stldi"
    assert d.confidence == "high"


def test_excepted_benefits_detected():
    d = detect_regime(
        signals_from_fields({"payer_name": "Liberty HealthShare"}, [],
                            document_text_blobs=["A health care sharing ministry — this is not insurance."])
    )
    assert d.regime == "excepted_coverage"


def test_pace_routes_to_handoff_not_a_regime():
    d = detect_regime(signals_from_fields({}, [], document_text_blobs=[
        "Program of All-Inclusive Care for the Elderly (PACE) enrollment"]))
    assert d.regime is None and d.handoff == "pace"


def test_grandfathered_notice_sets_attribute():
    d = detect_regime(
        signals_from_fields({"payer_name": "Aetna", "group_number": "G", "rx_bin": "6"}, [],
                            document_text_blobs=["Notice of Grandfathered Status: this plan is grandfathered."])
    )
    assert d.attributes.get("grandfathered") is True
    assert d.regime == "state_regulated_commercial"  # the notice never changes the regime


def test_empty_signals_are_ambiguous_not_commercial():
    d = detect_regime(signals_from_fields({}, []))
    assert d.regime is None  # NEVER silently defaults to commercial
    assert d.method == "ambiguous"
    assert d.confidence == "low"


def test_conflicting_commercial_and_mbi_is_ambiguous():
    # A clean commercial card but an MBI-shaped member id → real conflict, don't claim.
    d = detect_regime(
        signals_from_fields(
            {"payer_name": "Cigna", "group_number": "G9", "rx_bin": "610502", "member_id": "1EG4TE5MK73"},
            [],
        )
    )
    assert d.regime is None
    assert d.method == "ambiguous"
    assert d.candidate == "state_regulated_commercial"  # best guess to preselect, but unconfirmed


def test_qmb_language_raises_dual_confidence_and_sets_attribute():
    d = detect_regime(
        signals_from_fields(
            {"member_id": "1EG4TE5MK73", "payer_name": "Medicaid"},
            [],
            document_text_blobs=["You are a Qualified Medicare Beneficiary and should not be billed."],
        )
    )
    assert d.regime == "dual_eligible"
    assert d.confidence == "high"
    assert d.attributes.get("qmb_status") is True  # the never-bill check keys on this


def test_self_pay_only_when_declared_and_no_coverage():
    d = detect_regime(signals_from_fields({}, [], self_pay_declared=True))
    assert d.regime == "self_pay"
    assert d.method == "user_declared"
    # But a declared self-pay flag does NOT override real coverage evidence.
    d2 = detect_regime(signals_from_fields({"payer_name": "Aetna", "group_number": "G", "rx_bin": "6"}, [], self_pay_declared=True))
    assert d2.regime == "state_regulated_commercial"


def test_is_valid_regime():
    assert is_valid_regime("state_regulated_commercial")
    assert is_valid_regime("dual_eligible")
    assert is_valid_regime("stldi")
    assert not is_valid_regime("commercial")  # the retired v1 value is no longer valid
    assert not is_valid_regime("medicare")  # not one of the 14 exact values
    assert not is_valid_regime(None)
