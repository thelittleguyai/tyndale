"""Upload 503 after the real-OCR flip (2026-07-06).

The Azure DI SDK is synchronous; running poller.result() inline in the async upload handler
blocked the event loop for seconds, starving the health probe → Container Apps restarted the
replica mid-request → a 503 with no CORS headers ("Failed to fetch"). Fix: offload the DI call
to a thread, and DEGRADE (never crash, never fake text) when DI is unavailable. These tests
lock the degradation + that upload error responses still carry CORS headers."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources.extraction import run_document_ocr

_ORIGIN = "http://localhost:8081"  # an allowed dev origin (Expo web)


# --- pure degradation: real OCR + no/placeholder creds → error result, never fake, never crash
@pytest.mark.parametrize(
    "endpoint,key",
    [
        (None, None),  # unset
        ("<from terraform output>", "<placeholder>"),  # literal placeholder that got copied in
        ("not-a-url", "abc"),  # malformed endpoint
    ],
)
def test_run_document_ocr_degrades_under_real_ocr(monkeypatch, endpoint, key):
    s = get_settings()
    monkeypatch.setattr(s, "use_real_ocr", True)
    monkeypatch.setattr(s, "azure_doc_intelligence_endpoint", endpoint)
    monkeypatch.setattr(s, "azure_doc_intelligence_key", key)
    r = asyncio.run(run_document_ocr({"content_base64": "", "filename": "bill.pdf"}))
    assert r["extraction_status"] == "error"
    assert r["ocr_text"] == ""  # NEVER fabricated stub text under real OCR


def test_stub_mode_unaffected(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "use_real_ocr", False)
    r = asyncio.run(run_document_ocr({"content_base64": "", "filename": "bill.pdf"}))
    assert r.get("ocr_text")  # the deterministic stub still returns text in dev


# --- insurance card: real OCR + no DI creds must DEGRADE, never fabricate a card
def test_run_insurance_card_ocr_degrades_under_real_ocr(monkeypatch):
    from app.sources.insurance_card import run_insurance_card_ocr

    s = get_settings()
    monkeypatch.setattr(s, "use_real_ocr", True)
    monkeypatch.setattr(s, "azure_doc_intelligence_endpoint", None)
    monkeypatch.setattr(s, "azure_doc_intelligence_key", None)
    r = asyncio.run(run_insurance_card_ocr(b"fake-card-bytes"))
    assert r["fields"] == {}  # NO fabricated "Blue Shield PPO" / "JANE Q PUBLIC" card
    assert r.get("_stub") is False  # never the realistic stub under real OCR
    assert r.get("error")  # an honest failure reason is recorded


def test_insurance_card_stub_mode_unaffected(monkeypatch):
    from app.sources.insurance_card import run_insurance_card_ocr

    monkeypatch.setattr(get_settings(), "use_real_ocr", False)
    r = asyncio.run(run_insurance_card_ocr(b"fake-card-bytes"))
    assert r.get("_stub") is True  # explicit fixture mode still returns the deterministic card
    assert r["fields"]


# --- route: upload must NOT 503 when real OCR has no creds; it degrades and persists
@pytest.mark.asyncio
async def test_upload_succeeds_when_real_ocr_has_no_creds(client: AsyncClient, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "use_real_ocr", True)
    monkeypatch.setattr(s, "azure_doc_intelligence_endpoint", None)
    monkeypatch.setattr(s, "azure_doc_intelligence_key", None)

    r = await client.post(
        "/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 tiny", "application/pdf")}
    )
    assert r.status_code == 200, r.text  # NOT a 503 — the document is stored, OCR degraded
    case_id = r.json()["case_file_id"]

    async with AsyncSessionLocal() as sess:
        cf = (
            await sess.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
    doc = (cf.documents or [])[-1]
    assert doc["extraction_status"] == "error"  # honest failure recorded on the document


# --- CORS headers on a forced error response from the upload route
@pytest.mark.asyncio
async def test_upload_error_response_carries_cors_headers(client: AsyncClient, monkeypatch):
    async def _boom(*_a, **_k):
        raise HTTPException(status_code=503, detail="Upload storage is temporarily unavailable")

    monkeypatch.setattr("app.routes.upload._persist", _boom)
    r = await client.post(
        "/v1/upload",
        files={"file": ("bill.pdf", b"pdf", "application/pdf")},
        headers={"Origin": _ORIGIN},
    )
    assert r.status_code == 503
    # The app can render `detail` only if the error response is CORS-decorated (not an
    # ingress/replica-death 503, which is what the blocking DI call used to cause).
    assert r.headers.get("access-control-allow-origin") == _ORIGIN
    assert r.json()["detail"]  # the user-facing reason is present
