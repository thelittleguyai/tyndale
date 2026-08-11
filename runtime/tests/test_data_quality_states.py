"""Data-quality detection → Brock's §5.1 / §5.2 copy (conformance F3 / F4).

The copy was authored and unused because nothing detected the conditions. The assertions that
matter are the NEGATIVE ones: neither detector may fire on a healthy upload, and a partially
recovered number must be discarded rather than approximated.
"""

from __future__ import annotations

import pytest

from app.agents.context_loader import orchestration_step
from app.sources.data_quality import looks_like_summary_bill, never_approximate, partial_read


def _d(name="bill.pdf", status="extracted", chars=900, dtype="bill", text=""):
    return {
        "filename": name, "extraction_status": status, "ocr_text_chars": chars,
        "document_type": dtype, "ocr_text_preview": text,
    }


# --- F3 §5.1: the MIXED case only -------------------------------------------
def test_partial_read_fires_only_when_some_read_and_some_did_not():
    mixed = partial_read([_d("bill.pdf"), _d("eob.pdf", status="error", chars=0)])
    assert mixed is not None
    assert mixed["readable"] == ["bill.pdf"] and mixed["unreadable"] == ["eob.pdf"]
    assert mixed["unreadable_label"] == "eob.pdf"  # names the part specifically (§5.1)


@pytest.mark.parametrize(
    "docs",
    [
        [_d("a.pdf"), _d("b.pdf")],  # everything read — nothing to say
        [_d("a.pdf", status="error", chars=0)],  # everything failed — that's extraction_failed
        [_d("a.pdf", status="error", chars=0), _d("b.pdf", status="error", chars=0)],
        [],
    ],
)
def test_partial_read_stays_silent_outside_the_mixed_case(docs):
    assert partial_read(docs) is None


def test_a_fragment_counts_as_unreadable_not_readable():
    """OCR returning 12 characters is not a read — treating it as one is how a half-read
    document becomes an authoritative-looking audit."""
    out = partial_read([_d("good.pdf"), _d("fragment.pdf", chars=12)])
    assert out and out["unreadable"] == ["fragment.pdf"]


def test_multiple_unreadable_files_get_a_countable_label():
    out = partial_read([_d("ok.pdf"), _d("x.pdf", chars=0), _d("y.pdf", chars=0)])
    assert out["unreadable_label"] == "2 of your files"


def test_partial_values_are_discarded_never_approximated():
    """§5.1: "I won't guess at a number on your bill." The guard is explicit and named so the
    rule is greppable — a half-recovered total must never reach the user."""
    assert never_approximate("1,2??.00") is None
    assert never_approximate(1240) is None


def test_partial_copy_renders_with_the_named_part():
    text = orchestration_step("dataquality_partial_illegible", line_desc="eob.pdf")
    assert "eob.pdf" in text
    assert "won't guess at a number" in text
    assert "{" not in text


# --- F4 §5.2: summary vs itemized -------------------------------------------
_SUMMARY_TEXT = (
    "STATEMENT SUMMARY\nAccount 12345\nBALANCE FORWARD 0.00\n"
    "TOTAL CHARGES $2,347.18\nAMOUNT DUE $612.40\nPlease pay this amount by 04/01.\n"
    "Thank you for choosing Beloit Health System for your care this year.\n"
)
_ITEMIZED_TEXT = (
    "ITEMIZED STATEMENT OF CHARGES\nCPT 99284 Emergency dept visit $1,850.00\n"
    "CPT 70553 MRI brain $497.18\nHCPCS A9579 contrast $120.00\nTOTAL CHARGES $2,347.18\n"
)


def test_summary_bill_is_detected():
    assert looks_like_summary_bill(_d(dtype="bill", text=_SUMMARY_TEXT)) is True


def test_itemized_bill_is_not_a_summary():
    """The false-positive that would matter most: coaching someone to request the itemised
    bill they already sent."""
    assert looks_like_summary_bill(_d(dtype="bill", text=_ITEMIZED_TEXT)) is False


@pytest.mark.parametrize(
    "doc",
    [
        _d(dtype="eob", text=_SUMMARY_TEXT),  # an EOB is not a bill
        _d(dtype="bill", text="STATEMENT SUMMARY"),  # too little read to judge structure
        _d(dtype="bill", text="STATEMENT SUMMARY\n" + "no charges here at all. " * 12),  # no money
        _d(dtype="insurance_card", text=_SUMMARY_TEXT),
    ],
)
def test_summary_detection_requires_positive_evidence_on_both_sides(doc):
    assert looks_like_summary_bill(doc) is False


def test_summary_copy_degrades_rather_than_inventing_a_request_script():
    """§5.2 interpolates {itemized_request_script}, which has no authored value yet — so the
    string degrades instead of putting words in the user's mouth for a phone call."""
    text = orchestration_step("dataquality_summary_not_itemized")
    assert "{" not in text and text
