"""Prose grounding — drop-if-basis, scrub-if-incidental (2026-08-18, Phil's ruling).

Canary codes (70553 / A9579 / 36000) are used exactly as the e2e harness uses them: any
appearing in an output while absent from the documents is the fabrication tripwire. The
load-bearing properties: basis-dependence drops the whole finding; only cleanly-strippable
(parenthesized) incidental references scrub; inline mentions are never hand-edited into
Franken-prose (they drop instead); bare numbers without code context can never convict.
"""

from app.sources.prose_grounding import (
    ground_finding,
    prose_mentions,
    regeneration_instruction,
    strip_spans,
    structured_code_claims,
    summary_ungrounded_codes,
)

HAYSTACK = (
    "ACME HOSPITAL\nBELOIT WI 53511\nDATE OF SERVICE 03/14/2026\n"
    "73721 MRI LOWER EXTREMITY 1,850.00\n99213 OFFICE VISIT 185.00"
)


# ── basis: a structural code no document contains drops the finding ───────────────────────
def test_basis_code_absent_from_documents_drops_the_finding():
    verdict = ground_finding(
        {"code": "70553", "gap": 1200.0}, None, None, HAYSTACK
    )
    assert verdict.action == "drop" and verdict.dropped_codes == ["70553"]


def test_grounded_structured_claims_keep():
    verdict = ground_finding(
        {"cpt_code": "73721", "line_item_id": "li-1"},
        {"citations": [{"marker": "x"}]},
        {"action": "Call the billing office."},
        HAYSTACK,
    )
    assert verdict.action == "keep" and not verdict.scrubbed


def test_code_claims_walk_nested_structures():
    claims = structured_code_claims(
        {"lines": [{"procedure_code": "73721"}, {"hcpcs": "A9579"}], "note": "ignored"}
    )
    assert claims == {"73721", "A9579"}


# ── incidental: parenthesized scrubs; inline drops; ungrounded-basis drops ────────────────
def test_parenthesized_incidental_reference_is_scrubbed_when_grounding_is_real():
    verdict = ground_finding(
        {"line_item_id": "li-1", "description": "Doubled imaging like an MRI brain (70553)"},
        None,
        None,
        HAYSTACK,
    )
    assert verdict.action == "keep"
    assert "70553" not in str(verdict.scrubbed["facts"])
    assert "MRI brain" in verdict.scrubbed["facts"]["description"]


def test_inline_mention_is_never_franken_prosed_it_drops_instead():
    verdict = ground_finding(
        {"line_item_id": "li-1", "description": "You were billed CPT 70553 twice."},
        None,
        None,
        HAYSTACK,
    )
    assert verdict.action == "drop" and "70553" in verdict.dropped_codes


def test_prose_mention_without_any_real_grounding_drops():
    verdict = ground_finding(
        {"description": "Phantom service (A9579) suspected."}, None, None, HAYSTACK
    )
    assert verdict.action == "drop" and verdict.dropped_codes == ["A9579"]


# ── conviction rules: context-anchored only, sub-4 always keeps ───────────────────────────
def test_bare_numbers_zip_codes_and_dollars_never_convict():
    text = "Beloit WI 53511 billed 1850.00 on 03/14/2026 under account 98765"
    assert prose_mentions(text) == []
    verdict = ground_finding({"line_item_id": "li-1", "description": text}, None, None, HAYSTACK)
    assert verdict.action == "keep" and not verdict.scrubbed


def test_sub_four_char_codes_always_keep():
    verdict = ground_finding({"code": "J1"}, None, None, HAYSTACK)
    assert verdict.action == "keep"


# ── the summary path ──────────────────────────────────────────────────────────────────────
def test_summary_detection_flags_only_ungrounded_context_codes():
    dirty = "The MRI (70553) was billed twice; the office visit (99213) is consistent."
    assert summary_ungrounded_codes(dirty, HAYSTACK) == ["70553"]
    clean = "The MRI (73721) was billed twice."
    assert summary_ungrounded_codes(clean, HAYSTACK) == []


def test_regeneration_instruction_names_the_codes_and_forbids_meta_talk():
    text = regeneration_instruction(["70553"])
    assert "70553" in text and "Do not mention this correction" in text


def test_strip_spans_leaves_tidy_text():
    s = "An MRI of the brain (70553) done twice."
    spans = [(m[0], m[1]) for m in prose_mentions(s)]
    assert strip_spans(s, spans) == "An MRI of the brain done twice."
