"""Azure Document Intelligence OCR tools (real + stub-fallback).

`bill_ocr_extract` runs the prebuilt-document model on uploaded bytes.
`upload_extract_coverage` and `upload_extract_eob` are V1-Lite uploaded-document
shims that return Coverage/EOB-shaped dicts so subagents can be source-agnostic
(same return shape as the deferred FHIR tools per the integration contract).

All three respect the `use_real_ocr` feature flag. When false (or when DI
credentials are missing), they fall back to the canned MRI fixture so the
walking skeleton works end-to-end without Azure creds.
"""

from __future__ import annotations

import base64
from typing import Any

import structlog

from app.config import get_settings
from app.stubs.ocr import stub_extract
from app.tools import register_tool

log = structlog.get_logger(__name__)


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


# --- bill_ocr_extract -------------------------------------------------------
async def _bill_ocr_extract(args: dict[str, Any]) -> dict[str, Any]:
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
        "pages": [{"page_number": p.page_number, "width": p.width, "height": p.height} for p in (result.pages or [])],
        "key_value_pairs": [
            {"key": (kv.key.content if kv.key else None), "value": (kv.value.content if kv.value else None)}
            for kv in (result.key_value_pairs or [])
        ],
        "tables_count": len(result.tables or []),
    }


register_tool(
    "bill_ocr_extract",
    {
        "description": (
            "Run Azure Document Intelligence prebuilt-document OCR on a bill / EOB / insurance "
            "card image or PDF. Accepts content_base64 OR file_path. Returns ocr_text plus "
            "key_value_pairs the model can inspect."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_base64": {"type": "string"},
                "file_path": {"type": "string"},
                "filename": {"type": "string"},
            },
        },
    },
    _bill_ocr_extract,
)


# --- upload_extract_coverage ------------------------------------------------
async def _upload_extract_coverage(args: dict[str, Any]) -> dict[str, Any]:
    """V1-Lite Coverage extractor — same return shape as deferred fhir_get_coverage.

    Walking skeleton parses the OCR'd insurance-card text heuristically. Real
    field extraction with confidence scoring lands in Phase 2H (encounter
    verification UI surfaces low-confidence values for the user to correct).
    """
    raw = await _bill_ocr_extract(args)
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
        "coverage_terms_confidence": {"overall": 0.3, "notes": "V1-Lite OCR heuristics; user should confirm via encounter-verification UI"},
        "raw_ocr": raw,
    }


def _grep(text: str, prefixes: tuple[str, ...]) -> str | None:
    for p in prefixes:
        idx = text.find(p)
        if idx >= 0:
            after = text[idx + len(p):].strip()
            return after.splitlines()[0].strip() if after else None
    return None


register_tool(
    "upload_extract_coverage",
    {
        "description": (
            "Derive Coverage (plan/payer/deductible/coinsurance/OOP) from an uploaded "
            "insurance card image. Same return shape as fhir_get_coverage. Confidence "
            "is low (V1-Lite OCR heuristics) — flag uncertain fields for the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_base64": {"type": "string"},
                "file_path": {"type": "string"},
                "filename": {"type": "string"},
            },
        },
    },
    _upload_extract_coverage,
)


# --- upload_extract_eob -----------------------------------------------------
async def _upload_extract_eob(args: dict[str, Any]) -> dict[str, Any]:
    """V1-Lite EOB extractor — same return shape as deferred fhir_get_eobs."""
    raw = await _bill_ocr_extract(args)
    text = raw.get("ocr_text") or ""

    return {
        "eob": {
            "claim_id": _grep(text.upper(), ("CLAIM:", "CLAIM ID:")),
            "billed_amount": _first_dollar(text, ("BILLED",)),
            "allowed_amount": _first_dollar(text, ("ALLOWED",)),
            "patient_responsibility": _first_dollar(text, ("PATIENT RESPONSIBILITY", "YOU OWE", "MEMBER RESPONSIBILITY")),
            "remark_codes": [],
        },
        "raw_ocr": raw,
    }


def _first_dollar(text: str, anchors: tuple[str, ...]) -> float | None:
    import re

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


register_tool(
    "upload_extract_eob",
    {
        "description": (
            "Derive EOB (billed/allowed/patient responsibility + remark codes) from an "
            "uploaded EOB image or PDF. Same return shape as fhir_get_eobs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content_base64": {"type": "string"},
                "file_path": {"type": "string"},
                "filename": {"type": "string"},
            },
        },
    },
    _upload_extract_eob,
)
