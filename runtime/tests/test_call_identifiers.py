"""Typed call identifiers — claim/account numbers and contact phones (delta B4 / H6-L7).

Same discipline as `test_provider_extraction.py`: extracted TYPED at parse time (DL-39), never
regexed out of prose at render time; promoted from the document type that ASSIGNS each field;
absent rather than guessed. The harness assertion at the bottom is the one that matters most —
the pinned strip renders from typed data only, so a number can never reach a phone call
without having been extracted from a document first.
"""

from __future__ import annotations

from app.agents.context_loader import orchestration_step
from app.schemas.case_summary import GameplanStep
from app.sources.call_identifiers import (
    CallIdentifiers,
    derive_call_identifiers,
    for_party,
    of_case,
    script_variables,
)
from app.sources.extraction import grep_account_number, grep_claim_number, grep_contact_phone
from app.sources.gameplan import build_gameplan
from scripts.backfill_call_identifiers import derive_identifiers

# A provider statement in the Beloit shape (the live test case) and a payer EOB in the
# synthetic suite's shape. Real documents put these fields on a labelled line; both layouts
# below (inline and label-above-value) occur in the wild.
BILL_TEXT = """Beloit Health System
Patient: JANE DOE   Account #: 1821709
Statement Date: 08/01/2026
Questions about your bill? Call (608) 364-5011
Total Due $1,204.50
"""

EOB_TEXT = """EXPLANATION OF BENEFITS
Claim Number: TST20260514
Date of Service 05/14/2026
Member Services: 1-800-555-0142
Patient Responsibility $612.40
"""


# --- extraction ------------------------------------------------------------------------
def test_bills_carry_account_numbers():
    assert grep_account_number(BILL_TEXT) == "1821709"
    assert grep_account_number("ACCOUNT NUMBER\n  24-A88301-01\n") == "24-A88301-01"
    assert grep_account_number("Patient Account: 5567123") == "5567123"


def test_eobs_carry_claim_numbers():
    assert grep_claim_number(EOB_TEXT) == "TST20260514"
    assert grep_claim_number("DCN 2026137000123") == "2026137000123"
    assert grep_claim_number("Claim No. 24-A88301-01") == "24-A88301-01"


def test_identifier_extraction_fails_to_none_never_wrong():
    """Every failure mode returns None, because a WRONG number read aloud on a call is worse
    than no number: it sends the user to the wrong record and burns the call."""
    assert grep_claim_number("") is None
    assert grep_account_number("Total due $1,204.50") is None  # no anchor
    assert grep_claim_number("Claim Number: 05/14/2026") is None  # a date, not an ID
    assert grep_account_number("Account #: (608) 364-5011") is None  # a phone, not an ID
    assert grep_account_number("Account: 608-364-5011") is None  # ...also unformatted
    assert grep_claim_number("Claim Number: N/A") is None  # no digits


def test_an_id_sharing_a_line_with_a_phone_is_still_found():
    assert grep_account_number("Acct #: 1821709   Phone: (608) 364-5011") == "1821709"


def test_contact_phone_requires_a_contact_anchor():
    """"Never guessed": a phone-shaped digit run is not evidence that it's the number to
    call. Only a number the document labels as its contact is extracted — and nothing is ever
    looked up externally."""
    assert grep_contact_phone(BILL_TEXT) == "(608) 364-5011"
    assert grep_contact_phone(EOB_TEXT) == "1-800-555-0142"
    assert grep_contact_phone("Beloit Health System 608-364-5011") is None  # bare, unlabelled
    assert grep_contact_phone("Questions? Call us at 608.364.5011") == "608.364.5011"
    assert grep_contact_phone("") is None


# --- promotion: the right field from the right document type ---------------------------
def _bill(**kw):
    return {"document_type": "bill", "account_number": "1821709", "contact_phone": "(608) 364-5011", **kw}


def _eob(**kw):
    return {"document_type": "eob", "claim_number": "TST20260514", "contact_phone": "1-800-555-0142", **kw}


def test_each_field_is_promoted_from_the_document_type_that_assigns_it():
    ids = derive_call_identifiers([_bill(), _eob()])
    assert ids.claim_number == "TST20260514"  # payer-issued
    assert ids.account_number == "1821709"  # provider-issued
    assert ids.provider_phone == "(608) 364-5011"  # the number ON the bill
    assert ids.payer_phone == "1-800-555-0142"  # the number ON the EOB


def test_a_number_is_never_attributed_to_the_wrong_party():
    """A bill that happens to print a claim number does not make it the payer's, and an
    insurance card's phone is not the billing office's."""
    ids = derive_call_identifiers(
        [_bill(claim_number="TST20260514"), {"document_type": "insurance_card", "contact_phone": "1-800-000-0000"}]
    )
    assert ids.claim_number is None  # the bill's claim number isn't promoted
    assert ids.payer_phone is None  # nor is the card's phone
    assert ids.account_number == "1821709"


def test_multi_document_cases_keep_first_hit_and_leave_the_rest_addressable():
    """Three EOBs = three claim numbers. The case column carries the primary; the per-document
    entries stay the truth, which is why extraction writes them per document."""
    docs = [_eob(claim_number="CLM-1"), _eob(claim_number="CLM-2"), _eob(claim_number="CLM-3")]
    assert derive_call_identifiers(docs).claim_number == "CLM-1"
    assert [d["claim_number"] for d in docs] == ["CLM-1", "CLM-2", "CLM-3"]


def test_empty_and_malformed_documents_degrade_to_nulls():
    assert derive_call_identifiers(None) == CallIdentifiers()
    assert derive_call_identifiers([]) == CallIdentifiers()
    assert derive_call_identifiers(["not-a-dict", {"document_type": "bill"}]) == CallIdentifiers()


# --- party routing ---------------------------------------------------------------------
def test_the_reference_follows_who_is_being_called():
    ids = CallIdentifiers("TST20260514", "1821709", "(608) 364-5011", "1-800-555-0142")
    payer = for_party(ids, "payer")
    assert (payer.reference_kind, payer.reference_number, payer.phone) == (
        "claim",
        "TST20260514",
        "1-800-555-0142",
    )
    provider = for_party(ids, "provider")
    assert (provider.reference_kind, provider.reference_number, provider.phone) == (
        "account",
        "1821709",
        "(608) 364-5011",
    )


def test_a_missing_reference_is_not_substituted_from_the_other_party():
    """Quoting an account number to a payer wastes the call. Availability never overrides
    correctness — the honest state is no reference at all."""
    account_only = CallIdentifiers(account_number="1821709")
    assert for_party(account_only, "payer").reference_number is None
    assert for_party(account_only, "provider").reference_number == "1821709"


# --- the registry variable resolver ----------------------------------------------------
def test_present_values_resolve_in_an_authored_string(monkeypatch):
    from app.agents import context_loader

    registry = dict(context_loader.load_orchestration_registry())
    registry["b4_probe"] = context_loader.ScriptEntry(
        text="Tell them you're calling about claim {claim_number}.", tier="A", source="TEST"
    )
    monkeypatch.setattr(context_loader, "load_orchestration_registry", lambda: registry)

    ids = CallIdentifiers(claim_number="TST20260514")
    assert (
        orchestration_step("b4_probe", **script_variables(ids))
        == "Tell them you're calling about claim TST20260514."
    )


def test_a_missing_value_degrades_rather_than_rendering_blank(monkeypatch):
    """His §0 rule 2. The slot is omitted from the variables (not passed as ""), which is what
    routes an unfillable string to the §5 degradation variant instead of "claim ." — and the
    raw token never leaks either way."""
    from app.agents import context_loader

    registry = dict(context_loader.load_orchestration_registry())
    registry["b4_probe"] = context_loader.ScriptEntry(
        text="Tell them you're calling about claim {claim_number}.", tier="A", source="TEST"
    )
    monkeypatch.setattr(context_loader, "load_orchestration_registry", lambda: registry)

    rendered = orchestration_step("b4_probe", **script_variables(CallIdentifiers()))
    assert "{claim_number}" not in rendered
    assert "claim ." not in rendered
    assert rendered != "Tell them you're calling about claim ."


def test_script_variables_omits_empty_values():
    assert script_variables(CallIdentifiers()) == {}
    assert script_variables(CallIdentifiers(claim_number="X1")) == {"claim_number": "X1"}


# --- the pinned strip renders from typed data only -------------------------------------
class _Finding:
    """The minimum a gameplan step needs. Deliberately carries an account number in its PROSE:
    the strip must stay empty, because the only path to the strip is a typed field."""

    finding_id = "f-1"
    finding_type = "provider_side"
    category = "duplicate_charge"
    legal_claim = {"claim": "Account 1821709 was billed twice for the same line item."}
    recommendation = {"action": "Ask them to void the duplicate."}
    facts = {"gap": 389.0}


def _steps(identifiers=None) -> list[GameplanStep]:
    return build_gameplan([_Finding()], identifiers)


def test_the_pinned_strip_renders_only_from_typed_fields():
    """The harness assertion (B4). With no typed identifiers the step carries none — even
    though an account number is sitting in the finding's own claim text."""
    step = _steps()[0]
    assert step.reference_number is None and step.reference_kind is None and step.phone is None
    assert "1821709" in step.script.the_problem  # it IS in the prose…
    assert step.reference_number is None  # …and that is not a source


def test_a_typed_identifier_reaches_the_step():
    ids = CallIdentifiers(account_number="1821709", provider_phone="(608) 364-5011")
    step = _steps(ids)[0]
    assert step.party == "provider"
    assert (step.reference_kind, step.reference_number) == ("account", "1821709")
    assert step.phone == "(608) 364-5011"


def test_reference_kind_is_null_whenever_the_number_is():
    """The client keys its label off `reference_kind`; a kind with no number would render a
    bare "Account #" with nothing after it."""
    step = _steps(CallIdentifiers(claim_number="TST20260514"))[0]  # provider call, claim only
    assert step.reference_number is None and step.reference_kind is None


# --- backfill: structured sources only --------------------------------------------------
class _Case:
    def __init__(self, documents=None, eobs=None, **cols):
        self.documents = documents or []
        self.eobs = eobs or []
        for f in ("claim_number", "account_number", "provider_phone", "payer_phone"):
            setattr(self, f, cols.get(f))


def test_backfill_prefers_the_typed_document_field():
    ids = derive_identifiers(_Case(documents=[_bill(), _eob()]))
    assert ids.account_number == "1821709" and ids.claim_number == "TST20260514"


def test_backfill_greps_the_ocr_preview_when_no_typed_field():
    case = _Case(
        documents=[
            {"document_type": "bill", "ocr_text_preview": BILL_TEXT},
            {"document_type": "eob", "ocr_text_preview": EOB_TEXT},
        ]
    )
    ids = derive_identifiers(case)
    assert ids.account_number == "1821709"
    assert ids.claim_number == "TST20260514"
    assert ids.provider_phone == "(608) 364-5011"
    assert ids.payer_phone == "1-800-555-0142"


def test_backfill_salvages_the_legacy_eob_claim_id():
    """The pre-B4 extractor stored the whole rest of the line. Only the first token survives,
    and only if it validates as an identifier."""
    assert derive_identifiers(
        _Case(eobs=[{"eob": {"claim_id": "TST20260514  DOS 05/14/2026"}}])
    ).claim_number == "TST20260514"
    assert derive_identifiers(_Case(eobs=[{"eob": {"claim_id": "05/14/2026"}}])).claim_number is None
    assert derive_identifiers(_Case(eobs=[{"eob": {"claim_id": ""}}])).claim_number is None


def test_backfill_never_reads_finding_prose_and_leaves_null_when_absent():
    """No structured artifact → NULL. The Record row and the call script both degrade
    correctly there; a guessed number would not be recoverable downstream."""
    assert derive_identifiers(_Case()) == CallIdentifiers()
    assert derive_identifiers(_Case(documents=[{"document_type": "unclassified"}])) == CallIdentifiers()


def test_of_case_reads_the_typed_columns():
    case = _Case(claim_number=" TST20260514 ", account_number="", provider_phone=None)
    ids = of_case(case)
    assert ids.claim_number == "TST20260514"  # trimmed
    assert ids.account_number is None  # empty string is absent, not ""
