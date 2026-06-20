"""Azure Document Intelligence OCR tools (real + stub-fallback).

`bill_ocr_extract` runs the prebuilt-document model on uploaded bytes (the engine
lives in app/sources/extraction.py). `upload_extract_coverage` and
`upload_extract_eob` are V1-Lite uploaded-document shims that, as of CO-12A, run
BEHIND the data-interface seam (app/sources): each resolves its registered
adapter (CoverageSource → UserUploadedSBC, ClaimsSource → UserUploadedEOB) and
returns that adapter's payload.

The return shape is unchanged byte-for-byte — `coverage` / `eob` + `raw_ocr`
(plus `coverage_terms_confidence` for coverage) — PLUS an additive `provenance`
block (DL-69). Existing keys are never removed or renamed, so the subagents that
call these tools are unaffected (zero agent change). All three still respect the
`use_real_ocr` flag via the shared engine.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.sources import resolve
from app.sources.base import ClaimsSource, CoverageSource
from app.sources.extraction import run_document_ocr
from app.tools import register_tool

log = structlog.get_logger(__name__)


# --- bill_ocr_extract -------------------------------------------------------
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
    run_document_ocr,
)


# --- upload_extract_coverage ------------------------------------------------
async def _upload_extract_coverage(args: dict[str, Any]) -> dict[str, Any]:
    """V1-Lite Coverage extractor — runs behind CoverageSource (app/sources).

    Same return shape as the deferred fhir_get_coverage (coverage +
    coverage_terms_confidence + raw_ocr), plus an additive `provenance` block."""
    result = await resolve(CoverageSource).get_coverage(args.get("case_file_id", ""), args)
    return {**result.data, "provenance": result.provenance.model_dump(mode="json")}


register_tool(
    "upload_extract_coverage",
    {
        "description": (
            "Derive Coverage (plan/payer/deductible/coinsurance/OOP) from an uploaded "
            "insurance card image. Same return shape as fhir_get_coverage. Confidence "
            "is low (V1-Lite OCR heuristics) — flag uncertain fields for the user. "
            "Carries a provenance block (adapter/source_kind/as_of/confidence/assumptions)."
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
    """V1-Lite EOB extractor — runs behind ClaimsSource (app/sources).

    Same return shape as the deferred fhir_get_eobs (eob + raw_ocr), plus an
    additive `provenance` block."""
    result = await resolve(ClaimsSource).get_claims(args.get("case_file_id", ""), args)
    return {**result.data, "provenance": result.provenance.model_dump(mode="json")}


register_tool(
    "upload_extract_eob",
    {
        "description": (
            "Derive EOB (billed/allowed/patient responsibility + remark codes) from an "
            "uploaded EOB image or PDF. Same return shape as fhir_get_eobs. Carries a "
            "provenance block (adapter/source_kind/as_of/confidence/assumptions)."
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
