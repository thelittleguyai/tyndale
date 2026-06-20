"""V1-Lite OCR extraction engine + payload builders (the source-layer primitive).

``run_document_ocr`` runs Azure Document Intelligence (with stub fallback) on
uploaded bytes. ``extract_coverage_payload`` / ``extract_eob_payload`` turn that
OCR into the Coverage / EOB dict shapes the case file uses — the EXACT shapes the
``upload_extract_{coverage,eob}`` tools returned before CO-12A.

These live in app/sources/ (not app/tools/) so the data-interface adapters own
extraction without depending back on the tool layer. ``app.tools.ocr_tools`` (the
``bill_ocr_extract`` tool) and ``app.routes.upload`` call ``run_document_ocr``
from here. Logic moved verbatim from ocr_tools.py in CO-12A — behavior-identical.
"""

from __future__ import annotations

import base64
import re
from typing import Any

import structlog

from app.config import get_settings
from app.stubs.ocr import stub_extract

log = structlog.get_logger(__name__)

# V1-Lite OCR is heuristic; both upload extractors report the same low confidence.
V1_LITE_OCR_CONFIDENCE = 0.3


def _read_bytes(args: dict[str, Any]) -> tuple[bytes, str]:
    """Tools accept either base64-encoded bytes or a local file path."""
    if "content_base64" in args:
        return base64.b64decode(args["content_base64"]), args.get("filename", "upload.bin")
    if "file_path" in args:
        with open(args["file_path"], "rb") as fh:
            return fh.read(), args["file_path"].rsplit("/", 1)[-1]
    raise ValueError("ocr tool requires content_base64 or file_path")


def _di_client():
    """Lazy-import the Azure DI client so import-time doesn't require the SDK.

    Returns None for any of:
      * endpoint or key unset
      * endpoint doesn't start with https:// (e.g. literal placeholder
        '<from terraform output>' values that got copied into .env.local)
    so callers can fall back to the stub instead of crashing on a bogus URL.
    """
    settings = get_settings()
    endpoint = settings.azure_doc_intelligence_endpoint or ""
    key = settings.azure_doc_intelligence_key or ""
    if not endpoint.startswith("https://") or not key or key.startswith("<"):
        log.warning(
            "ocr.di_endpoint_or_key_invalid_falling_back_to_stub",
            endpoint_set=bool(endpoint),
            endpoint_looks_real=endpoint.startswith("https://"),
            key_set=bool(key),
        )
        return None
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    return DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )


async def run_document_ocr(args: dict[str, Any]) -> dict[str, Any]:
    """Azure Document Intelligence prebuilt-document OCR (stub fallback).

    Backs the ``bill_ocr_extract`` tool and the upload route. Was
    ``ocr_tools._bill_ocr_extract`` before CO-12A."""
    settings = get_settings()
    content, filename = _read_bytes(args)

    if not settings.use_real_ocr:
        return stub_extract(filename, content)

    client = _di_client()
    if client is None:
        log.warning("ocr.di_credentials_missing", filename=filename)
        return stub_extract(filename, content)

    poller = client.begin_analyze_document("prebuilt-document", body=content)
    result = poller.result()

    # Compact projection — keep the full Result accessible via 'raw' for the agent
    # to introspect via subsequent calls if it needs more.
    return {
        "filename": filename,
        "byte_count": len(content),
        "ocr_text": (result.content or "")[:50000],
        "pages": [
            {"page_number": p.page_number, "width": p.width, "height": p.height}
            for p in (result.pages or [])
        ],
        "key_value_pairs": [
            {
                "key": (kv.key.content if kv.key else None),
                "value": (kv.value.content if kv.value else None),
            }
            for kv in (result.key_value_pairs or [])
        ],
        "tables_count": len(result.tables or []),
    }


def _grep(text: str, prefixes: tuple[str, ...]) -> str | None:
    for p in prefixes:
        idx = text.find(p)
        if idx >= 0:
            after = text[idx + len(p) :].strip()
            return after.splitlines()[0].strip() if after else None
    return None


def _first_dollar(text: str, anchors: tuple[str, ...]) -> float | None:
    upper = text.upper()
    for anchor in anchors:
        idx = upper.find(anchor)
        if idx < 0:
            continue
        window = text[idx : idx + 200]
        m = re.search(r"\$?\s*([0-9]{1,3}(?:[,0-9]{0,9})?(?:\.[0-9]{2})?)", window)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


async def extract_coverage_payload(args: dict[str, Any]) -> dict[str, Any]:
    """Coverage dict from an uploaded insurance card — the pre-CO-12A
    ``upload_extract_coverage`` return: {coverage, coverage_terms_confidence, raw_ocr}.

    Walking skeleton parses the OCR'd insurance-card text heuristically; real field
    extraction with per-value confidence surfaces in the encounter-verification UI."""
    raw = await run_document_ocr(args)
    text = (raw.get("ocr_text") or "").upper()

    coverage = {
        "plan_name": _grep(text, ("PLAN:", "PLAN NAME:", "GROUP NAME:")),
        "payer_name": _grep(text, ("PAYER:", "INSURER:", "INSURANCE:")),
        "member_id": _grep(text, ("MEMBER ID:", "ID:", "SUBSCRIBER ID:")),
        "deductible_amount": None,
        "deductible_met": None,
        "coinsurance_percent": None,
        "oop_max_amount": None,
        "oop_max_met": None,
        "network_tier": None,
    }
    return {
        "coverage": coverage,
        "coverage_terms_confidence": {
            "overall": V1_LITE_OCR_CONFIDENCE,
            "notes": "V1-Lite OCR heuristics; user should confirm via encounter-verification UI",
        },
        "raw_ocr": raw,
    }


async def extract_eob_payload(args: dict[str, Any]) -> dict[str, Any]:
    """EOB dict from an uploaded EOB — the pre-CO-12A ``upload_extract_eob``
    return: {eob, raw_ocr}."""
    raw = await run_document_ocr(args)
    text = raw.get("ocr_text") or ""

    return {
        "eob": {
            "claim_id": _grep(text.upper(), ("CLAIM:", "CLAIM ID:")),
            "billed_amount": _first_dollar(text, ("BILLED",)),
            "allowed_amount": _first_dollar(text, ("ALLOWED",)),
            "patient_responsibility": _first_dollar(
                text, ("PATIENT RESPONSIBILITY", "YOU OWE", "MEMBER RESPONSIBILITY")
            ),
            "remark_codes": [],
        },
        "raw_ocr": raw,
    }
