"""The extracted-string plausibility gate (Brock field test 2026-08-22): statement-ledger
furniture ("Payments (since last statements)", from the UMC El Paso page-1 summary) reached the
attest copy's {patient_name} slot as a person. The gate rejects ledger vocabulary, field-label
shapes, and parenthetical/empty/overlong strings at the extraction root AND at every persisted
read seam, degrading to the honest generic form — no value beats a wrong value."""

from types import SimpleNamespace

from app.routes.record import _row_provider
from app.sources.data_quality import looks_like_summary_bill
from app.sources.extraction import (
    grep_patient_name,
    grep_provider_name,
    plausible_extracted_name,
)

_UMC_TEXT = (
    "UNIVERSITY MEDICAL CENTER OF EL PASO    Page 1 of 4\n"
    "PATIENT: Payments (since last statements)\n"
    "STATEMENT SUMMARY\n"
    "Previous Balance    $2,480.00\n"
    "Payments (since last statements)    -$500.00\n"
    "New Balance    $1,980.00\n"
    "AMOUNT DUE    $1,980.00\n"
    "PLEASE PAY THIS AMOUNT\n"
    "Account Number 4471982\n"
)


def test_ledger_furniture_is_not_a_name():
    junk = [
        "Payments (since last statements)",
        "Payment (since last statement)",
        "Balance",
        "AMOUNT DUE:",
        "Total Charges",
        "(see reverse)",
        "Account Number 4471",
        "Previous Balance",
        "Statement Summary",
        "PAY THIS AMOUNT",
        "Page 1 of 4",
        "x" * 81,
        "ab",
        "   ",
        None,
        1234,
    ]
    for v in junk:
        assert not plausible_extracted_name(v), v


def test_real_names_pass_the_gate():
    real = [
        "MARIA G LOPEZ",
        "O'Brien, Patrick",
        "Jane Doe-Smith",
        "UNIVERSITY MEDICAL CENTER OF EL PASO",
        "Maple Grove Family Medicine",
    ]
    for v in real:
        assert plausible_extracted_name(v), v


def test_umc_statement_grep_returns_none_not_the_ledger_label():
    # The bare PATIENT anchor matches the misextraction line — the gate turns a wrong name
    # into no name (→ callers degrade), never into copy.
    assert grep_patient_name(_UMC_TEXT) is None


def test_real_anchored_names_still_grep():
    assert (
        grep_patient_name("PATIENT NAME:  MARIA G LOPEZ   ACCOUNT #: 4471982\n")
        == "MARIA G LOPEZ"
    )
    assert (
        grep_provider_name("PROVIDER: Maple Grove Family Medicine  NPI: 999\n")
        == "Maple Grove Family Medicine"
    )


def test_record_row_provider_gates_persisted_junk():
    junk = SimpleNamespace(
        provider_name="Payments (since last statements)", eobs=[], documents=[]
    )
    assert _row_provider(junk) is None
    real = SimpleNamespace(provider_name="Umc El Paso", eobs=[], documents=[])
    assert _row_provider(real) == "Umc El Paso"


def test_umc_page_one_classifies_as_summary_bill():
    # Debrief finding (2026-08-22): the "1 of 4" statement IS caught by the existing
    # summary-bill classifier once typed 'bill' — it routes dataquality_summary_not_itemized
    # → the itemized-bill request, i.e. the needs-documents path, not a full audit.
    assert looks_like_summary_bill(
        {"document_type": "bill", "ocr_text_preview": _UMC_TEXT}
    )
