"""Plan Library copy rule (Sprint D, DL-87): user-facing strings in the plan-proposal flow
present the numbers and ask "does this match?" — they NEVER reveal that a value came from
another user or from a shared library. Provenance stays in internal fields only."""

from __future__ import annotations

import uuid

from app.db.models.plan_library import PlanLibraryEntry
from app.services.plan_library import propose

# Phrases that would leak the DL-73 provenance boundary into a user-facing string.
BANNED_SUBSTRINGS = [
    "other user",
    "another user",
    "other member",
    "someone else",
    "our library",
    "the library",
    "plan library",
    "plan_library",
    "we saw this",
    "we've seen",
    "based on data we have",
    "from our records of",
    "provenance",
    "de-identified",
]


def _entry() -> PlanLibraryEntry:
    return PlanLibraryEntry(
        plan_library_id=uuid.uuid4(),
        payer="Blue Cross Blue Shield",
        plan_name="PPO Silver 2026",
        plan_year=2026,
        benefit_design={"deductible_amount": 2500, "coinsurance_percent": 20},
        confidence=3,
    )


def _user_facing_strings(payload: dict) -> list[str]:
    """The strings a user could read. payer/plan_name/summary are the plan's OWN identity
    (fine to show); we still scan them all for provenance leaks. benefit_design values are
    numbers, not provenance."""
    out = [str(payload.get("summary", "")), str(payload.get("payer", "")), str(payload.get("plan_name", ""))]
    return [s.lower() for s in out if s]


def test_proposal_summary_has_no_provenance_leak():
    payload = propose(_entry())
    strings = _user_facing_strings(payload)
    for s in strings:
        for banned in BANNED_SUBSTRINGS:
            assert banned not in s, f"user-facing string leaked provenance ({banned!r}): {s!r}"


def test_summary_presents_numbers_and_asks_confirmation():
    payload = propose(_entry())
    summary = payload["summary"].lower()
    # It shows the plan + numbers and asks the user to confirm.
    assert "2026" in payload["summary"]
    assert "deductible" in summary
    assert "?" in payload["summary"]  # it asks, rather than asserting provenance


def test_summary_with_bare_payer_still_clean():
    entry = _entry()
    entry.plan_name = None  # falls back to payer as the display name
    payload = propose(entry)
    for banned in BANNED_SUBSTRINGS:
        assert banned not in payload["summary"].lower()
