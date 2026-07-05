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


# (coverage fields, document types) -> expected regime + minimum confidence
_CASES = [
    # medicare_traditional: an MSN is unambiguous document evidence.
    ("medicare_traditional_msn", {"member_id": "1EG4TE5MK73"}, ["msn"], "medicare_traditional", "high"),
    # medicare_traditional: bare MBI, no MA branding.
    ("medicare_traditional_mbi", {"member_id": "1EG4TE5MK73"}, [], "medicare_traditional", "medium"),
    # medicare_advantage: commercial payer + a Medicare product name.
    ("ma_branding", {"payer_name": "UnitedHealthcare", "plan_name": "Medicare Advantage Complete"}, [], "medicare_advantage", "medium"),
    # medicare_advantage: an MA EOB document is high-confidence format evidence.
    ("ma_eob_doc", {"payer_name": "Humana", "plan_name": "Gold Plus"}, ["ma_eob"], "medicare_advantage", "high"),
    # medicaid: MCO/state-plan branding.
    ("medicaid_branding", {"payer_name": "MassHealth"}, [], "medicaid", "medium"),
    # dual_qmb: BOTH Medicare and Medicaid evidence.
    ("dual", {"member_id": "1EG4TE5MK73", "payer_name": "Medicaid Managed Care"}, [], "dual_qmb", "medium"),
    # tricare_va
    ("tricare", {"payer_name": "TRICARE East (Humana Military)"}, [], "tricare_va", "medium"),
    ("va_statement", {"payer_name": "Department of Veterans Affairs"}, ["va_statement"], "tricare_va", "high"),
    # commercial: brand + group + Rx, no government moniker.
    ("commercial", {"payer_name": "Aetna", "plan_name": "PPO", "group_number": "G1", "rx_bin": "610502"}, [], "commercial", "high"),
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
    assert d.candidate == "commercial"  # best guess to preselect, but unconfirmed


def test_qmb_language_raises_dual_confidence():
    d = detect_regime(
        signals_from_fields(
            {"member_id": "1EG4TE5MK73", "payer_name": "Medicaid"},
            [],
            document_text_blobs=["You are a Qualified Medicare Beneficiary and should not be billed."],
        )
    )
    assert d.regime == "dual_qmb"
    assert d.confidence == "high"


def test_self_pay_only_when_declared_and_no_coverage():
    d = detect_regime(signals_from_fields({}, [], self_pay_declared=True))
    assert d.regime == "self_pay"
    assert d.method == "user_declared"
    # But a declared self-pay flag does NOT override real coverage evidence.
    d2 = detect_regime(signals_from_fields({"payer_name": "Aetna", "group_number": "G", "rx_bin": "6"}, [], self_pay_declared=True))
    assert d2.regime == "commercial"


def test_is_valid_regime():
    assert is_valid_regime("commercial")
    assert is_valid_regime("dual_qmb")
    assert not is_valid_regime("medicare")  # not one of the seven exact values
    assert not is_valid_regime(None)
