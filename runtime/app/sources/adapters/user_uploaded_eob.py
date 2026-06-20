"""UserUploadedEOB — ClaimsSource adapter over the V1-Lite OCR upload path.

Extracts the insurer's EOB from an uploaded document (today's
``upload_extract_eob`` logic, now in app/sources/extraction.py) and wraps it with
Provenance. The EOB is the insurer's CLAIM — extracted to be audited, never
adopted as the answer. A future fhir_get_eobs / OneUpHealth adapter registers
behind the same ClaimsSource interface with zero agent change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.provenance import Provenance
from app.sources.base import ClaimsResult
from app.sources.extraction import V1_LITE_OCR_CONFIDENCE, extract_eob_payload


class UserUploadedEOB:
    """Implements ClaimsSource (structural / Protocol)."""

    adapter_name = "UserUploadedEOB"

    async def get_claims(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> ClaimsResult:
        payload = await extract_eob_payload(args or {})
        return ClaimsResult(
            data=payload,
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="user_upload",
                as_of=None,
                confidence=V1_LITE_OCR_CONFIDENCE,
                assumptions=[
                    "V1-Lite OCR heuristics; figures are the insurer's claim, audited not adopted"
                ],
            ),
        )


if TYPE_CHECKING:
    from app.sources.base import ClaimsSource

    _: ClaimsSource = UserUploadedEOB()  # structural-conformance check (mypy)
