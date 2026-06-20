"""UserUploadedSBC — CoverageSource adapter over the V1-Lite OCR upload path.

Extracts coverage from an uploaded insurance card / SBC (today's
``upload_extract_coverage`` logic, now in app/sources/extraction.py) and wraps it
with Provenance. A future OneUpHealthCoverage adapter registers behind the same
CoverageSource interface with zero agent change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.provenance import Provenance
from app.sources.base import CoverageResult
from app.sources.extraction import V1_LITE_OCR_CONFIDENCE, extract_coverage_payload


class UserUploadedSBC:
    """Implements CoverageSource (structural / Protocol)."""

    adapter_name = "UserUploadedSBC"

    async def get_coverage(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> CoverageResult:
        payload = await extract_coverage_payload(args or {})
        overall = (payload.get("coverage_terms_confidence") or {}).get(
            "overall", V1_LITE_OCR_CONFIDENCE
        )
        return CoverageResult(
            data=payload,
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="user_upload",
                as_of=None,
                confidence=float(overall),
                assumptions=["V1-Lite OCR heuristics; user confirms low-confidence fields"],
            ),
        )


if TYPE_CHECKING:
    from app.sources.base import CoverageSource

    _: CoverageSource = UserUploadedSBC()  # structural-conformance check (mypy)
