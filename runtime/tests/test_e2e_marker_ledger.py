"""Fabrication-canary scan (Brock 2026-09-17): the ledgered benign signature is NARROW —
Bill Detective analyst notes naming a marker while reasoning about the CPT FAMILY of a code
genuinely on the bill. Every other field, and that field without both conditions, trips.
Pure functions, tested with explicit markers so the assertions survive a canary re-pick."""

import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "e2e_scenarios"))

from run_scenarios import _retrying, _warm  # noqa: E402
from run_scenarios import (  # noqa: E402
    FIXTURE_MARKERS,
    _bill_codes,
    _marker_benign,
    _marker_hits,
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

def test_final_canary_set_is_structurally_unassigned():
    assert FIXTURE_MARKERS == ("02417", "05821", "Z4411")
    for m in ("02417", "05821"):  # the five-digit CPT gap between anesthesia and surgery
        assert 2000 <= int(m) <= 9999 and len(m) == 5
    assert FIXTURE_MARKERS[2][0] == "Z"  # HCPCS Level II letter never nationally assigned
    assert _marker_hits("05821", "code 05821 billed") and not _marker_hits("05821", "cost 105821.00")


def test_warm_up_retries_a_cold_target_then_gives_up():
    """2026-09-18: a scale-to-zero cold start blew the 30 s preflight. The warm-up retries
    with a delay and only exits once every attempt failed."""
    calls: list[int] = []
    slept: list[float] = []

    def flaky() -> None:
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("cold")

    assert _warm(flaky, attempts=3, delay_s=2.0, sleep=slept.append) == 3
    assert slept == [2.0, 2.0]

    def dead() -> None:
        raise ConnectionError("down")

    with pytest.raises(SystemExit, match="cannot reach target after 2 attempts"):
        _warm(dead, attempts=2, delay_s=0.0, sleep=slept.append)


def test_retrying_returns_the_value_and_treats_a_5xx_as_transient():
    """The mid-cutover 500 on test-token (sweep 35378477176): a 5xx raised inside fetch is
    retried like a transport error and the eventual response is returned."""
    seen: list[int] = []

    def mint():
        seen.append(1)
        if len(seen) == 1:
            raise RuntimeError("test-token 500: internal_server_error")
        return {"status": 200}

    assert _retrying(mint, attempts=4, delay_s=0.0, sleep=lambda _s: None, what="test-token") == {"status": 200}
    assert len(seen) == 2
