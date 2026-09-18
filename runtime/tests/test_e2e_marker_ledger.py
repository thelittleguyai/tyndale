"""Fabrication-canary scan (Brock 2026-09-17): the ledgered benign signature is NARROW —
Bill Detective analyst notes naming a marker while reasoning about the CPT FAMILY of a code
genuinely on the bill. Every other field, and that field without both conditions, trips.
Pure functions, tested with explicit markers so the assertions survive a canary re-pick."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "e2e_scenarios"))

from run_scenarios import (  # noqa: E402
    _bill_codes,
    _marker_benign,
    _scan_audit_markers,
)

# The exact 2026-08-25 signature (captured_bill_photo, --inspect): a 70551 bill, notes naming
# the family siblings.
_NOTE = (
    "Only 70551 billed — the without-contrast variant (lowest complexity of the "
    "70551/70552/70553 family); no upcoding signal. Single line item, single DOS."
)
_EXTRACT = {"line_items": [{"code": "70551", "billed_amount": 1200.0}]}


def _audit_with(path_field: str, text: str) -> dict:
    facts = {"notes": text} if path_field == "notes" else {"summary": text}
    return {
        "findings": [{"category": "diagnostic_complete_no_errors_found", "facts": facts}],
        "summary": "ok",
    }


def test_family_reasoning_in_notes_is_ledgered_not_failed():
    fails, ledgered = _scan_audit_markers(
        _audit_with("notes", _NOTE), _bill_codes(_EXTRACT), markers=("70553",)
    )
    assert fails == []
    assert ledgered and "ledgered: canary:family_reasoning_in_notes" in ledgered[0]


def test_same_note_without_the_family_code_on_the_bill_trips():
    fails, _ = _scan_audit_markers(
        _audit_with("notes", _NOTE), _bill_codes({"line_items": [{"code": "99213"}]}),
        markers=("70553",),
    )
    assert fails and "leaked" in fails[0]


def test_notes_hit_without_family_language_trips():
    fails, _ = _scan_audit_markers(
        _audit_with("notes", "Consider 70553 as an alternative charge."),
        _bill_codes(_EXTRACT), markers=("70553",),
    )
    assert fails


def test_any_other_field_trips_even_with_family_language():
    fails, ledgered = _scan_audit_markers(
        _audit_with("summary", _NOTE), _bill_codes(_EXTRACT), markers=("70553",)
    )
    assert fails and ledgered == []


def test_allow_rule_is_marker_agnostic_and_prefix_scoped():
    # a re-picked marker shares no family with anything real -> the rule can never fire for it
    assert _marker_benign("02417", "$.findings[0].facts.notes", "02417 family reasoning", {"70551"}) is None
    assert _marker_benign("70553", "$.findings[0].facts.notes", _NOTE, {"70551"}) is not None

