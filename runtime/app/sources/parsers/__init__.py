"""Document parsers (Sprint E). Turn classified OCR text into the normalized EOB-like
shape the accumulator consumes, tagged with source_type + typed provenance.

Wave 1 (built): ``msn`` (Medicare Summary Notice), ``ma_eob`` (Medicare Advantage Part C
EOB). Waves 2–3 are typed stubs that raise a clear NotImplemented until built.

Each parser emits a ``ParsedDocument``: a list of wrapped claim dicts (``{"eob": {...},
"source_type": ..., "field_confidence": {...}}`` — extra keys are ignored by the accumulator,
which unwraps ``entry["eob"]``), plus a doc-level Provenance and the regime the document
IMPLIES. A document's implied regime that disagrees with the case's confirmed regime raises
a finding (``regime_consistency_finding``) — never a silent override (Independent Audit
Doctrine).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sources.parsers.ma_eob import parse_ma_eob
from app.sources.parsers.msn import parse_msn

# Which coverage regime each document type implies (14-value populations, Brock 2026-07-06).
IMPLIED_REGIME: dict[str, str] = {
    "msn": "medicare_traditional",
    "ma_eob": "medicare_advantage",
    "mco_notice": "medicaid_mco",
    "tricare_eob": "tricare",
    "va_statement": "va_champva",
}

# dual_eligible legitimately holds both Medicare and Medicaid documents, so those don't clash.
_REGIME_COMPATIBLE: dict[str, set[str]] = {
    "dual_eligible": {
        "medicare_traditional", "medicare_advantage", "medicaid_ffs", "medicaid_mco",
    },
}

# Wave 2–3 types with no parser yet. Classified + stored, but not parsed to claims.
STUB_DOCUMENT_TYPES: tuple[str, ...] = (
    "mco_notice",
    "gfe",
    "tricare_eob",
    "va_statement",
    "community_care_auth",
)


@dataclass
class ParsedDocument:
    source_type: str
    regime_implied: str | None
    claims: list[dict] = field(default_factory=list)  # wrapped {"eob": {...}, ...} dicts
    provenance: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "regime_implied": self.regime_implied,
            "claims": list(self.claims),
            "provenance": dict(self.provenance),
            "assumptions": list(self.assumptions),
        }


_PARSERS = {
    "msn": parse_msn,
    "ma_eob": parse_ma_eob,
}


def parse_document(document_type: str, text: str) -> ParsedDocument | None:
    """Parse a classified document into claims. Returns None for types without a parser
    (wave 2–3 stubs / non-claim documents) — the caller keeps the raw document."""
    parser = _PARSERS.get(document_type)
    if parser is None:
        return None
    return parser(text)


def regime_consistency_finding(source_type: str, case_regime: str | None) -> dict | None:
    """A finding spec when a document's implied regime disagrees with the case's confirmed
    regime — surfaced, never silently overridden (DL-82). None when consistent, unknown, or
    the case regime legitimately spans both (dual_qmb)."""
    implied = IMPLIED_REGIME.get(source_type)
    if implied is None or not case_regime or case_regime == implied:
        return None
    if implied in _REGIME_COMPATIBLE.get(case_regime, set()):
        return None
    return {
        "finding_type": "data_consistency",
        "category": "regime_document_mismatch",
        "subagent_source": "document_parser",
        "voice_tier": "A",
        "facts": {
            "document_source_type": source_type,
            "document_implies_regime": implied,
            "case_coverage_regime": case_regime,
        },
        "recommendation": {
            "action": (
                f"Confirm the coverage type: this looks like a {implied.replace('_', ' ')} "
                f"document, but the case is set to {case_regime.replace('_', ' ')}."
            ),
            "reasoning": (
                "The uploaded document's format implies a different coverage population than "
                "the one on file. Tyndale flags the mismatch rather than silently switching, "
                "so the right rules corpus is applied."
            ),
        },
    }
