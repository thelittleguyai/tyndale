"""Typed provider_name + date_of_service extraction/backfill (Record row follow-up 2026-07-15).
The provider is extracted TYPED at parse time (DL-39), never regexed out of finding prose; the
backfill fills existing cases from structured artifacts only, leaving null where none exist."""

from __future__ import annotations

import datetime

import pytest

from app.sources.extraction import grep_patient_name, grep_provider_name
from scripts.backfill_provider_name import derive_provider_and_dos


class _Case:
    def __init__(self, documents=None, eobs=None, provider_name=None, date_of_service=None):
        self.documents = documents or []
        self.eobs = eobs or []
        self.provider_name = provider_name
        self.date_of_service = date_of_service


def test_grep_provider_name_extracts_and_preserves_case():
    assert grep_provider_name("PROVIDER: Maple Grove Family Medicine\nDOS 04/02/2026") == "Maple Grove Family Medicine"
    assert grep_provider_name("Rendering Provider   Beloit Health System") == "Beloit Health System"
    assert grep_provider_name("Billed by: Northside Imaging Center") == "Northside Imaging Center"


def test_grep_provider_name_fails_to_none_never_wrong():
    assert grep_provider_name("") is None
    assert grep_provider_name("total amount due $1,200.00") is None  # no anchor
    assert grep_provider_name("PROVIDER: 04/02/2026") is None  # a date, not a name
    assert grep_provider_name("PROVIDER: $1,200") is None  # mostly digits/punct


def test_derive_prefers_typed_doc_field():
    case = _Case(documents=[{"provider_name": "Maple Grove Family Medicine", "date_of_service": "2026-04-02"}])
    provider, dos = derive_provider_and_dos(case)
    assert provider == "Maple Grove Family Medicine"
    assert dos == datetime.date(2026, 4, 2)


def test_derive_greps_ocr_preview_when_no_typed_field():
    case = _Case(documents=[{"ocr_text_preview": "Provider: Beloit Health System\nDate of Service: 10/15/2025"}])
    provider, dos = derive_provider_and_dos(case)
    assert provider == "Beloit Health System"
    assert dos == datetime.date(2025, 10, 15)


def test_derive_falls_back_to_eob_then_null():
    assert derive_provider_and_dos(_Case(eobs=[{"eob": {"provider": "Community Clinic"}}]))[0] == "Community Clinic"
    # nothing structured → (None, None); the Record row uses its fallback title, correctly.
    assert derive_provider_and_dos(_Case()) == (None, None)
    assert derive_provider_and_dos(_Case(documents=[{"ocr_text_preview": "just some text, no provider"}])) == (None, None)


# --- second-field truncation (found by the §A2 attest harness scenario) ------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Documents routinely put a SECOND field on the anchor's line. Without truncation the
        # account number lands in the attest audit payload as the "patient name as extracted".
        ("Patient: MARGARET R. OTHERPERSON    Account #: E2E-01", "MARGARET R. OTHERPERSON"),
        ("Patient: JANE DOE Account #: 99213", "JANE DOE"),  # single-space variant
        ("Member Name: ROBERT L SMITH DOB: 01/02/1955", "ROBERT L SMITH"),
        ("Patient: Maria de la Cruz MRN: 4471", "Maria de la Cruz"),  # lowercase particles kept
        ("PATIENT NAME: Amy Fluegel", "Amy Fluegel"),  # nothing to truncate
    ],
)
def test_patient_name_stops_at_a_second_field(text, expected):
    assert grep_patient_name(text) == expected


def test_provider_name_gets_the_same_truncation():
    assert grep_provider_name("Provider: SYNTHETIC VALLEY MEDICAL CENTER NPI: 123") == (
        "SYNTHETIC VALLEY MEDICAL CENTER"
    )
