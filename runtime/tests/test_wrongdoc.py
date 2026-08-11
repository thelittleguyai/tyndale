"""Wrong-document redirect (§A2 state 2 / script §5ii).

The generic "not a medical bill" dead-end is typed per branch, each with its own next step —
and, critically, a document that COULD carry charges is never mislabeled a wrong document (that
would hide a real extraction failure behind friendly copy)."""

from __future__ import annotations

import pytest

from app.agents.context_loader import load_orchestration_registry, load_orchestration_script
from app.agents.orchestrator import not_a_bill_message
from app.agents.wrongdoc import classify_wrong_document
from app.analytics.events import REGISTRY, PropType


def _docs(*types) -> list[dict]:
    return [{"document_type": t, "filename": f"{t}.pdf"} for t in types]


@pytest.mark.parametrize(
    ("types", "branch", "next_action"),
    [
        (("insurance_card",), "card", "upload_card_flow"),
        (("sbc",), "sbc", "attach_to_coverage"),
        (("gfe",), "sbc", "attach_to_coverage"),  # a GFE is coverage-ish, not auditable
        (("clinical_record",), "clinical", "add_bill_or_eob"),
        (("unclassified",), "unknown", "add_bill_or_eob"),
        (("insurance_card", "sbc"), "card", "upload_card_flow"),  # card wins the pair
    ],
)
def test_branch_routing_and_next_action(types, branch, next_action):
    wrong = classify_wrong_document(_docs(*types))
    assert wrong is not None
    assert (wrong.branch, wrong.next_action) == (branch, next_action)
    assert wrong.key == f"wrongdoc.{branch}"


@pytest.mark.parametrize(
    "types",
    [("eob",), ("itemized_bill",), ("collections_notice",), ("denial_letter",), ("msn",),
     ("insurance_card", "eob"), ("sbc", "bill")],
)
def test_auditable_documents_are_never_a_wrong_document(types):
    """The load-bearing negative: if anything in the case could produce line items, its failure
    to do so is a REAL extraction problem — never dressed up as a wrong-document redirect."""
    assert classify_wrong_document(_docs(*types)) is None


def test_empty_input_is_not_a_branch():
    assert classify_wrong_document([]) is None
    assert classify_wrong_document(None) is None


def test_every_branch_has_authored_copy_and_names_the_detected_type():
    """Every branch key exists, and his §5.3 names the DETECTED DOCUMENT TYPE. (His authored
    version dropped the filename the prior engineering copy carried — flagged for him in the
    pull-in summary; his file is the authority.)"""
    reg = load_orchestration_registry()
    for branch in ("card", "sbc", "clinical", "unknown"):
        assert f"wrongdoc.{branch}" in reg
        assert reg[f"wrongdoc.{branch}"].source.startswith("§5.3")

    msg = not_a_bill_message(["card.pdf"], _docs("insurance_card"))
    assert "an insurance card" in msg  # {detected_doc_type} interpolated
    assert "{" not in msg  # no raw slot ever leaks


def test_branch_copy_is_brocks_authored_redirect():
    """His v1 authors ONE wrong-document string (§5.3) that TYPES ITSELF via
    {detected_doc_type}; our four branches all render it with their own detected type. Brock:
    author per-branch copy if you want them distinct (flagged in the summary)."""
    card = not_a_bill_message(["card.pdf"], _docs("insurance_card"))
    sbc = not_a_bill_message(["plan.pdf"], _docs("sbc"))
    assert "an insurance card" in card and "a plan summary" in sbc
    assert card != sbc  # distinct because the detected type differs
    assert "doesn't look like a medical bill" not in card  # the old engineering line is gone


def test_generic_fallback_survives_when_no_documents_are_passed():
    """Callers without document context (older call sites) still get the honest generic line."""
    msg = not_a_bill_message(["mystery.pdf"])
    assert "mystery.pdf" in msg


def test_analytics_branch_enum_matches_the_router():
    spec = REGISTRY["wrong_document_redirect"]
    assert spec.props["branch"].type is PropType.ENUM
    assert set(spec.props["branch"].values) == {"card", "sbc", "clinical", "unknown"}
