"""Layered document classifier (Sprint E).

Replaces the flat keyword scan with three layers, most-specific first:
  1. structure anchors — phrases unique to one document type (MSN's "Maximum You May Be
     Billed", a Good Faith Estimate header, a VA statement masthead);
  2. keyword heuristics — the prior walking-skeleton scan (eob / bill / card / plan_summary
     / denial / collections), preserved so existing classifications don't move;
  3. regime cross-check — population branding (Medicare Advantage, Medicaid MCO) that
     disambiguates an otherwise-generic EOB/notice into ma_eob / mco_notice.

Nothing matches → ``unclassified``. It never guesses — an ambiguous document is labeled
unclassified rather than forced into a type (Grounding Doctrine).

New wave-1..3 document types: msn, ma_eob, mco_notice, gfe, tricare_eob, va_statement,
community_care_auth. Parsers exist for wave 1 (msn, ma_eob); the rest are typed stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Benefit-summary markers (shared with app.routes.upload, which imports these). Acronyms
# are matched parenthesized so a bare "SBC"/"EOC" inside a bill doesn't false-positive.
BENEFITS_DOC_MARKERS: tuple[str, ...] = (
    "SUMMARY OF BENEFITS",
    "SCHEDULE OF BENEFITS",
    "SUMMARY PLAN DESCRIPTION",
    "BENEFIT SUMMARY",
    "PLAN SUMMARY",
    "CERTIFICATE OF COVERAGE",
    "EVIDENCE OF COVERAGE",
    "OUTLINE OF COVERAGE",
    "BENEFIT BOOKLET",
    "MEMBER HANDBOOK",
    "PLAN DOCUMENT",
    "COVERAGE SUMMARY",
    "BENEFITS AT A GLANCE",
    "CERTIFICATE OF INSURANCE",
    "(SBC)",
    "(SPD)",
    "(COC)",
    "(EOC)",
)

# Document types (existing + Sprint E wave 1–3). Unknown is "unclassified".
NEW_DOCUMENT_TYPES: tuple[str, ...] = (
    "msn",
    "ma_eob",
    "mco_notice",
    "gfe",
    "tricare_eob",
    "va_statement",
    "community_care_auth",
)


@dataclass
class ClassificationResult:
    document_type: str
    confidence: float
    method: str  # "structure" | "structure+regime" | "keyword" | "none"
    signals: list[str] = field(default_factory=list)

    def as_tuple(self) -> tuple[str, float]:
        return self.document_type, self.confidence


def _has(hay: str, *phrases: str) -> bool:
    return any(p in hay for p in phrases)


def classify_document(text: str | None, filename: str | None = None) -> ClassificationResult:
    """Classify an OCR'd document into one type + confidence + the signals that decided it."""
    # Normalize word separators so filenames (medicare_summary_notice) and OCR hyphenation
    # match the space-delimited anchors.
    hay = f"{(text or '').upper()} {(filename or '').upper()}".replace("_", " ").replace("-", " ")

    # --- Layer 1: structure anchors (specific documents) ---
    if _has(hay, "MEDICARE SUMMARY NOTICE", "MAXIMUM YOU MAY BE BILLED"):
        return ClassificationResult("msn", 0.95, "structure", ["medicare summary notice anchor"])
    if _has(hay, "GOOD FAITH ESTIMATE"):
        return ClassificationResult("gfe", 0.95, "structure", ["good faith estimate header"])
    if _has(hay, "TRICARE") and _has(hay, "EXPLANATION OF BENEFITS", "EOB"):
        return ClassificationResult("tricare_eob", 0.9, "structure", ["tricare + EOB"])
    if _has(hay, "DEPARTMENT OF VETERANS AFFAIRS", "VETERANS AFFAIRS", "VETERANS HEALTH") and _has(
        hay, "COPAY", "PATIENT STATEMENT", "STATEMENT OF ACCOUNT", "AMOUNT DUE"
    ):
        return ClassificationResult("va_statement", 0.9, "structure", ["VA + statement/copay"])
    if _has(hay, "COMMUNITY CARE") and _has(hay, "AUTHORIZATION", "AUTHORIZED", "REFERRAL"):
        return ClassificationResult(
            "community_care_auth", 0.9, "structure", ["community care authorization"]
        )

    is_eob = _has(hay, "EXPLANATION OF BENEFITS", "EOB", "MEMBER RESPONSIBILITY")

    # --- Layer 3 (applied before generic eob): regime cross-check disambiguation ---
    if is_eob and _has(hay, "MEDICARE ADVANTAGE", "PART C", "MEDICARE ADVANTAGE ORGANIZATION"):
        return ClassificationResult(
            "ma_eob", 0.9, "structure+regime", ["EOB + Medicare Advantage branding"]
        )
    if _has(hay, "MEDICAID", "MANAGED CARE") and _has(
        hay, "NOTICE OF ACTION", "ADVERSE BENEFIT DETERMINATION", "DENIAL", "DENIED", "NOT COVERED"
    ):
        return ClassificationResult(
            "mco_notice", 0.85, "structure+regime", ["Medicaid/MCO + notice/denial"]
        )

    # --- Layer 2: prior keyword heuristics (preserved) ---
    if is_eob:
        return ClassificationResult("eob", 0.9, "keyword", ["explanation of benefits"])
    if _has(hay, "MEMBER ID", "GROUP NUMBER", "RX BIN"):
        return ClassificationResult("insurance_card", 0.9, "keyword", ["card fields"])
    if _has(hay, *BENEFITS_DOC_MARKERS):
        return ClassificationResult("plan_summary", 0.85, "keyword", ["benefits-doc marker"])
    if _has(hay, "ADVERSE BENEFIT DETERMINATION", "DENIAL", "DENIED", "NOT COVERED"):
        return ClassificationResult("denial_letter", 0.8, "keyword", ["denial language"])
    if _has(hay, "COLLECTION", "PAST DUE", "FINAL NOTICE", "DELINQUENT"):
        return ClassificationResult("collections_notice", 0.8, "keyword", ["collections language"])
    if _has(hay, "AMOUNT DUE", "BILLED", "STATEMENT", "CPT"):
        return ClassificationResult("bill", 0.85, "keyword", ["billing language"])

    return ClassificationResult("unclassified", 0.4, "none", ["no matching signal"])
