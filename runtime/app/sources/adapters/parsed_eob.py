"""ParsedEobSource — a ClaimsSource that routes MSN / MA-EOB OCR text through the wave-1
parsers (Sprint E), emitting the normalized claims + typed Provenance (DL-68/69).

args: {document_type, ocr_text, coverage_regime}. For a document type without a wave-1
parser it returns an empty claim set (the caller keeps the raw document) rather than
guessing. The regime the document implies is cross-checked against the case's confirmed
regime; a clash rides back as ``regime_mismatch_finding`` for the orchestrator to persist —
never a silent override.
"""

from __future__ import annotations

from typing import Any

from app.schemas.provenance import Provenance
from app.sources.base import ClaimsResult
from app.sources.parsers import parse_document, regime_consistency_finding


class ParsedEobSource:
    adapter_name = "ParsedEobSource"

    async def get_claims(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> ClaimsResult:
        args = args or {}
        document_type = str(args.get("document_type") or "")
        parsed = parse_document(document_type, args.get("ocr_text") or "")

        if parsed is None:
            return ClaimsResult(
                data={"claims": [], "source_type": document_type},
                provenance=Provenance(
                    adapter=self.adapter_name,
                    source_kind="user_upload",
                    confidence=0.0,
                    assumptions=[f"no wave-1 parser for document_type={document_type!r}"],
                ),
            )

        mismatch = regime_consistency_finding(parsed.source_type, args.get("coverage_regime"))
        prov = parsed.provenance
        return ClaimsResult(
            data={
                "claims": parsed.claims,
                "source_type": parsed.source_type,
                "regime_implied": parsed.regime_implied,
                "regime_mismatch_finding": mismatch,
            },
            provenance=Provenance(
                adapter=prov.get("adapter", self.adapter_name),
                source_kind="user_upload",
                confidence=float(prov.get("confidence", 0.3)),
                assumptions=list(prov.get("assumptions", [])),
            ),
        )
