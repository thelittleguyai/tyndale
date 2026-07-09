"""Fixture data must never masquerade as real extraction (2026-07-06).

Live finding (case e06f7c3b): with real OCR + real Claude, uploading synthetic PDFs whose DI
extraction degraded produced an encounter screen showing the 5-item MRI *fixture* — none of it
from the user's documents. Root chain: DI 404'd (prebuilt-document removed in the GA API) ->
run_document_ocr degraded to empty text -> Bill Detective had nothing to translate ->
extract_line_items UNCONDITIONALLY fell back to _fixture_line_items().

These lock the fix: in real mode an empty translate degrades VISIBLY (status extraction_failed,
no fixtures, per-document error status surfaced); only explicit fixture mode (use_real False)
still serves fixtures."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import bill_detective, orchestrator
from app.agents.runner import RunResult
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile

_FIXTURE_MARKER = "70553"  # an MRI-fixture CPT code — its presence == fabricated line items


async def _fresh_case(client: AsyncClient) -> str:
    up = await client.post("/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 tiny", "application/pdf")})
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


def _force_real_claude(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "litellm_proxy_url", None)


@pytest.mark.asyncio
async def test_real_mode_empty_translate_degrades_no_fixtures(client: AsyncClient, monkeypatch):
    s = get_settings()
    # Force a deterministic OCR degradation on upload so the assertions hold regardless of the
    # ambient env: CI has no .env.local (use_real_ocr defaults False → the stub returns
    # 'extracted' text), so we pin real OCR ON with no DI creds → the DI-error path we're testing.
    monkeypatch.setattr(s, "use_real_ocr", True)
    monkeypatch.setattr(s, "azure_doc_intelligence_endpoint", None)
    monkeypatch.setattr(s, "azure_doc_intelligence_key", None)

    case_id = await _fresh_case(client)  # upload OCR degrades → doc extraction_status 'error'
    _force_real_claude(monkeypatch)

    # Bill Detective runs but persists NO line items (the empty-translate case, e.g. OCR degraded).
    async def _empty_translate(case_file_id, mode="translate"):
        return RunResult(final_text="", tool_calls=[], usage={})

    monkeypatch.setattr(bill_detective, "run", _empty_translate)

    result = await orchestrator.extract_line_items(case_id)

    # Degrades VISIBLY — never the fixture.
    assert result.status == "extraction_failed"
    assert result.line_items == []
    assert result.extraction_message  # honest, user-facing reason present
    blob = result.model_dump_json()
    assert _FIXTURE_MARKER not in blob  # NO fabricated MRI line items anywhere in the response

    # Per-document extraction status is surfaced (item 3). The uploaded PDF degraded under the
    # ambient real-OCR-with-placeholder-endpoint config, so it reads as an error with 0 chars.
    assert result.documents, "per-document extraction provenance must be surfaced"
    doc = result.documents[0]
    assert doc.extraction_status == "error"
    assert doc.ocr_text_chars == 0

    # And the case is persisted in the degraded state (not left mid-flight, not encounter-pending).
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert cf.status == "extraction_failed"
        assert not cf.line_items  # nothing fabricated was persisted either


@pytest.mark.asyncio
async def test_fixture_mode_still_serves_fixtures(client: AsyncClient, monkeypatch):
    case_id = await _fresh_case(client)
    # Explicit fixture mode: no real Claude. This is the ONLY path that may serve fixtures.
    monkeypatch.setattr(get_settings(), "use_real_claude", False)

    result = await orchestrator.extract_line_items(case_id)

    assert result.status == "encounter_verification_pending"
    assert result.line_items  # the deterministic fixture still drives dev/CI/demo
    assert any(li.code == _FIXTURE_MARKER for li in result.line_items)


@pytest.mark.asyncio
async def test_readable_but_not_a_bill_degrades_to_not_a_bill(client: AsyncClient, monkeypatch):
    # A document that READ fine but isn't a bill/EOB → the distinct honest 'not_a_bill' state,
    # naming the file — NEVER a 0-item encounter, never fixtures.
    async def _grocery_ocr(args):
        return {
            "filename": args.get("filename", "f"),
            "ocr_text": "milk eggs bread bananas cereal coffee",  # readable, but not a bill
            "extraction_status": "extracted",
            "byte_count": 10, "pages": [], "key_value_pairs": [], "tables_count": 0,
        }

    monkeypatch.setattr("app.routes.upload.run_document_ocr", _grocery_ocr)
    up = await client.post(
        "/v1/upload", files={"file": ("groceries.pdf", b"%PDF-1.4 milk eggs", "application/pdf")}
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]

    _force_real_claude(monkeypatch)

    async def _empty_translate(case_file_id, mode="translate"):
        return RunResult(final_text="", tool_calls=[], usage={})

    monkeypatch.setattr(bill_detective, "run", _empty_translate)

    result = await orchestrator.extract_line_items(case_id)
    assert result.status == "not_a_bill"
    assert result.line_items == []
    assert "groceries.pdf" in (result.extraction_message or "")  # names the file
    assert _FIXTURE_MARKER not in result.model_dump_json()  # no fabrication
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
    assert cf.status == "not_a_bill"
    assert not cf.line_items


@pytest.mark.asyncio
async def test_zero_item_invariant_never_reaches_encounter(client: AsyncClient, monkeypatch):
    # Belt-and-suspenders (item 4): even if the fixture path itself yields nothing, the case must
    # NEVER enter encounter_verification_pending with zero line items — it degrades honestly.
    case_id = await _fresh_case(client)
    monkeypatch.setattr(get_settings(), "use_real_claude", False)  # fixture mode
    monkeypatch.setattr(orchestrator, "_fixture_line_items", lambda: [])  # …that yields nothing

    result = await orchestrator.extract_line_items(case_id)
    assert result.status != "encounter_verification_pending"
    assert result.status == "extraction_failed"
    assert result.line_items == []
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
    assert cf.status != "encounter_verification_pending"
