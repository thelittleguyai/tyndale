"""The translate-grounding guard (dev sweep 2026-08-17).

A photographed bill's thin OCR let the Bill Detective echo its skill's worked example
("MRI brain w/ + w/o contrast (70553)") into PERSISTED line items — a fabricated charge
on the user's encounter screen, caught only because the example code doubles as a
fixture marker in the e2e harness. The guard is deterministic: a coded line item whose
base code appears in no uploaded document's OCR text did not come from the user's
documents, so it does not survive the translate seam.

The load-bearing property: conviction requires strong evidence. Legacy cases without
stored full text, uncoded rows, and short codes all KEEP — the guard only ever drops a
5-char-class code that is provably absent from every readable document.
"""

from types import SimpleNamespace

from app.agents.orchestrator import _grounded_line_items


def _cf(*docs: dict) -> SimpleNamespace:
    return SimpleNamespace(documents=list(docs))


def _doc(text: str | None, status: str = "extracted") -> dict:
    d: dict = {"filename": "doc.pdf", "extraction_status": status}
    if text is not None:
        d["ocr_text"] = text
    return d


BILL_TEXT = "ACME HOSPITAL\nDATE OF SERVICE 03/14/2026\n73721 MRI LOWER EXTREMITY 1850.00\n99213 OFFICE VISIT 185.00"


def test_grounded_items_survive_and_prompt_bleed_does_not():
    """The observed failure shape: real codes from the document plus the skill example's
    70553, which appears nowhere in any uploaded text."""
    items = [
        {"code": "73721", "raw_description": "MRI LOWER EXTREMITY"},
        {"code": "99213", "raw_description": "OFFICE VISIT"},
        {"code": "70553", "raw_description": "MRI BRAIN W/O & W/ CONTRAST"},
    ]
    kept, dropped = _grounded_line_items(_cf(_doc(BILL_TEXT)), items)
    assert [i["code"] for i in kept] == ["73721", "99213"]
    assert dropped == ["70553"]


def test_modifier_forms_are_grounded_by_their_base_code():
    kept, dropped = _grounded_line_items(
        _cf(_doc(BILL_TEXT)), [{"code": "73721-26", "raw_description": "professional component"}]
    )
    assert kept and not dropped


def test_uncoded_and_short_coded_rows_are_never_convicted():
    items = [{"code": "", "raw_description": "statement row"}, {"code": "J1", "raw_description": "?"}]
    kept, dropped = _grounded_line_items(_cf(_doc(BILL_TEXT)), items)
    assert len(kept) == 2 and not dropped


def test_legacy_cases_without_full_text_keep_everything():
    """Pre-guard uploads carry only the 1000-char preview — a long bill's codes may
    legitimately live past the cutoff, so absence there proves nothing."""
    legacy = {"filename": "old.pdf", "extraction_status": "extracted", "ocr_text_preview": "ACME"}
    kept, dropped = _grounded_line_items(
        SimpleNamespace(documents=[legacy]), [{"code": "70553", "raw_description": "MRI"}]
    )
    assert kept and not dropped


def test_error_documents_cannot_ground_anything():
    """A doc that failed extraction contributes no haystack; if it is the only doc, the
    guard has no evidence and keeps everything rather than convicting blind."""
    kept, dropped = _grounded_line_items(
        _cf(_doc("70553 SOMEHOW", status="error")), [{"code": "70553", "raw_description": "MRI"}]
    )
    assert kept and not dropped


def test_matching_is_case_insensitive_and_multi_document():
    eob = _doc("payer eob\ncode 70551 mri brain allowed 900.00")
    kept, dropped = _grounded_line_items(
        _cf(_doc(BILL_TEXT), eob), [{"code": "70551", "raw_description": "MRI BRAIN"}]
    )
    assert kept and not dropped
