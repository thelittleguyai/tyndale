"""B4 fresh-upload acceptance + check-in title treatment (2026-08-19, item 6).

Two walkthrough findings, pinned:

1. A FRESH upload of the Beloit-shaped statement (the live day-one case) must carry the
   call-mode strip's identifiers via the PARSE-TIME path: typed per-document fields at
   upload, promoted to the case's typed columns in the same request. And a case whose
   typed columns are empty stays degraded even though its stored OCR text contains the
   identifiers — the read path never re-greps prose (the backfill's structured-only rule
   is correct; nobody "fixes" it with a prose regex at read time).

2. The outcome check-in card drops its summary MID-SENTENCE ("…I helped you with {X}.
   Did it get resolved?") — the variable must be a sentence-position noun phrase, never
   'Cost sharing audit' with a stray capital.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from types import SimpleNamespace

from app.crons.outcome_followup import _summary_for
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources.call_identifiers import of_case

# The Beloit shape (mirrors tests/test_call_identifiers.py — synthetic values).
_BELOIT_TEXT = (
    "Beloit Health System\n"
    "Patient: JANE DOE   Account #: 1821709\n"
    "Statement — Amount Due $842.00\n"
    "Questions? Call (608) 364-5011\n"
)


@pytest.mark.asyncio
async def test_fresh_upload_carries_call_identifiers_at_parse_time(
    client: AsyncClient, monkeypatch
):
    import app.routes.upload as upload_route

    async def _beloit_ocr(args):
        return {"ocr_text": _BELOIT_TEXT, "extraction_status": "extracted"}

    monkeypatch.setattr(upload_route, "run_document_ocr", _beloit_ocr)

    r = await client.post(
        "/v1/upload",
        files=[("files", ("beloit-statement.pdf", b"%PDF-1.4 fresh", "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    cfid = r.json()["case_file_id"]

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))
        ).scalar_one()
        ids = of_case(case)
        # The call-mode strip's provider column, straight from typed columns.
        assert ids.account_number == "1821709"
        assert ids.provider_phone == "(608) 364-5011"
        await s.delete(case)
        await s.commit()


def test_degraded_old_case_stays_degraded_no_prose_regex_at_read():
    # Typed columns empty; the prose CONTAINS both identifiers. The read path must
    # return nulls — re-deriving from prose at read time is exactly the "fix" the
    # backfill's structured-only rule forbids.
    old = SimpleNamespace(
        claim_number=None,
        account_number=None,
        provider_phone=None,
        payer_phone=None,
        documents=[{"document_type": "bill", "ocr_text": _BELOIT_TEXT}],
    )
    ids = of_case(old)
    assert ids == (None, None, None, None)


def test_checkin_summary_is_sentence_position():
    rec = SimpleNamespace(
        category="cost_sharing_audit",
        recommendation={"action": "call"},
        facts={"payer_name": "UnitedHealthcare"},
    )
    s = _summary_for([rec])
    assert s == "the cost sharing audit with UnitedHealthcare"
    assert not s[0].isupper()  # never 'Cost sharing…' mid-sentence

    no_payer = SimpleNamespace(category="eob_discrepancy", recommendation={"action": "x"}, facts={})
    assert _summary_for([no_payer]) == "the EOB discrepancy"  # initialisms stay upper

    assert _summary_for([]) == "your case"
