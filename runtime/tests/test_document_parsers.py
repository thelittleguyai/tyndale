"""Document parsers, wave 1 (Sprint E): the layered classifier's new types, the MSN and
MA-EOB parsers (happy / partial / garbage), regime-consistency findings, and the typed
ParsedEobSource ClaimsSource wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.provenance import Provenance
from app.sources.adapters.parsed_eob import ParsedEobSource
from app.sources.document_classifier import classify_document
from app.sources.parsers import parse_document, regime_consistency_finding

_DOCS = Path(__file__).parent / "fixtures" / "documents"
_MSN = (_DOCS / "msn_sample.txt").read_text()
_MA_EOB = (_DOCS / "ma_eob_sample.txt").read_text()


# --- classifier ---
@pytest.mark.parametrize(
    "text,expected",
    [
        ("MEDICARE SUMMARY NOTICE — Maximum You May Be Billed $40", "msn"),
        ("EXPLANATION OF BENEFITS — Aetna Medicare Advantage Part C", "ma_eob"),
        ("NOTICE OF ACTION — your Medicaid managed care plan DENIED the service", "mco_notice"),
        ("GOOD FAITH ESTIMATE under the No Surprises Act", "gfe"),
        ("TRICARE Explanation of Benefits for sponsor", "tricare_eob"),
        ("Department of Veterans Affairs — patient statement, $15 copay amount due", "va_statement"),
        ("Community Care Network authorization / referral letter", "community_care_auth"),
        # preserved existing types
        ("EXPLANATION OF BENEFITS — member responsibility $50", "eob"),
        ("Member ID 123 Group Number 456 Rx Bin 789", "insurance_card"),
        ("Hospital STATEMENT Amount Due $1,200 CPT 70553", "bill"),
        ("Summary of Benefits and Coverage (SBC)", "plan_summary"),
        # never guesses
        ("a grocery receipt for bananas", "unclassified"),
    ],
)
def test_classifier(text, expected):
    assert classify_document(text).document_type == expected


def test_classifier_filename_signal():
    assert classify_document("", "2026_medicare_summary_notice.pdf").document_type == "msn"


# --- MSN parser ---
def test_msn_happy_path():
    doc = parse_document("msn", _MSN)
    assert doc.source_type == "msn"
    assert doc.regime_implied == "medicare_traditional"
    assert len(doc.claims) == 2
    first = doc.claims[0]["eob"]
    # The anchor: Maximum You May Be Billed → patient_responsibility.
    assert first["patient_responsibility"] == 36.0
    assert first["billed_amount"] == 250.0
    assert first["allowed_amount"] == 180.0
    assert first["date_of_service"] == "2026-03-15"
    assert first["deductible_ytd_stated"] == 203.0
    assert first["appeal_deadline"] == "2026-12-28"
    assert doc.claims[0]["field_confidence"]["patient_responsibility"] == 0.7
    assert doc.provenance["confidence"] == 0.6  # anchor found


def test_msn_partial_extraction_never_fabricates():
    doc = parse_document(
        "msn",
        "MEDICARE SUMMARY NOTICE\nClaim number: 5\nDate of Service: 02/01/2026\n",
    )
    assert len(doc.claims) == 1
    eob = doc.claims[0]["eob"]
    assert eob["date_of_service"] == "2026-02-01"
    assert eob["patient_responsibility"] is None  # not present → not fabricated
    assert eob["billed_amount"] is None
    assert doc.provenance["confidence"] == 0.3  # no anchor


def test_msn_garbage_input():
    doc = parse_document("msn", "the quick brown fox jumped over nothing billable")
    assert doc.claims == []
    assert doc.regime_implied == "medicare_traditional"
    assert any("no claims" in a for a in doc.assumptions)


# --- MA EOB parser ---
def test_ma_eob_happy_path():
    doc = parse_document("ma_eob", _MA_EOB)
    assert doc.source_type == "ma_eob"
    assert doc.regime_implied == "medicare_advantage"
    assert len(doc.claims) == 1
    eob = doc.claims[0]["eob"]
    assert eob["patient_responsibility"] == 140.0
    assert eob["amount_applied_to_oop"] == 140.0
    assert eob["oop_ytd_stated"] == 1200.0
    assert eob["date_of_service"] == "2026-05-10"
    assert eob["adjudication_date"] == "2026-05-20"
    assert eob["plan_paid"] == 760.0


def test_ma_eob_falls_back_to_member_responsibility_for_oop():
    doc = parse_document(
        "ma_eob",
        "EXPLANATION OF BENEFITS Medicare Advantage\nDate of service: 06/01/2026\n"
        "Your responsibility: $60.00\n",
    )
    eob = doc.claims[0]["eob"]
    # No explicit "applied to out-of-pocket" line → member cost-share is used.
    assert eob["amount_applied_to_oop"] == 60.0


def test_ma_eob_garbage_input():
    doc = parse_document("ma_eob", "nothing resembling an EOB here")
    assert doc.claims == []


# --- regime consistency ---
def test_regime_consistency_finding():
    mismatch = regime_consistency_finding("msn", "state_regulated_commercial")
    assert mismatch is not None
    assert mismatch["category"] == "regime_document_mismatch"
    assert mismatch["facts"]["document_implies_regime"] == "medicare_traditional"
    # consistent / compatible / unknown → no finding
    assert regime_consistency_finding("msn", "medicare_traditional") is None
    assert regime_consistency_finding("ma_eob", "dual_eligible") is None
    assert regime_consistency_finding("msn", None) is None


def test_stub_types_have_no_parser():
    for t in ("mco_notice", "gfe", "tricare_eob", "va_statement", "community_care_auth"):
        assert parse_document(t, "some text") is None


# --- typed ClaimsSource wiring ---
@pytest.mark.asyncio
async def test_parsed_eob_source_emits_typed_provenance():
    src = ParsedEobSource()
    result = await src.get_claims(
        "case-1", {"document_type": "msn", "ocr_text": _MSN, "coverage_regime": "state_regulated_commercial"}
    )
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.adapter == "MSNExtractor"
    assert result.provenance.confidence == 0.6
    assert len(result.data["claims"]) == 2
    # regime clash (MSN implies medicare_traditional, case is commercial) rides back.
    assert result.data["regime_mismatch_finding"] is not None


@pytest.mark.asyncio
async def test_parsed_eob_source_unknown_type_is_empty_not_guessed():
    src = ParsedEobSource()
    result = await src.get_claims("case-1", {"document_type": "gfe", "ocr_text": "x"})
    assert result.data["claims"] == []
    assert result.provenance.confidence == 0.0
