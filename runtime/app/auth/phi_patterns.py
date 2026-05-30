"""PHI pattern detection for the send_email guardrail (Phase CO-8 / DL-47).

Conservative regex + keyword scan over outbound email content. The bar is
"catches anything resembling PHI": FALSE POSITIVES ARE ACCEPTABLE (they just mean
the caller must switch to an allowlisted, vetted template), FALSE NEGATIVES ARE
NOT (real PHI must never leave Tyndale by email — DL-47). This is deliberately
coarse; it is NOT a medical NER and does not try to be precise.

Exported:
    PhiMatch          — one detected signal (pattern_type, matched_text, context, confidence)
    detect_phi(text)  — list[PhiMatch] over the given text ([] means "no PHI signal")
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_CONTEXT = 40  # chars of surrounding context captured per match


@dataclass(frozen=True)
class PhiMatch:
    pattern_type: str
    matched_text: str
    context: str  # ±40 chars around the match (newlines flattened)
    confidence: str  # "high" | "medium" | "low"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


# --- 1. Dollar amounts in a medical context ---------------------------------
_DOLLAR_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
_MEDICAL_MONEY_KEYWORDS = (
    "bill",
    "balance",
    "owe",
    "owed",
    "claim",
    "eob",
    "deductible",
    "coinsurance",
    "copay",
    "oop",
    "out-of-pocket",
    "out of pocket",
    "allowed",
    "billed",
    "charged",
    "payment",
    "member responsibility",
)
_MONEY_WINDOW = 80  # chars on each side of the $ amount to search for a keyword

# --- 2. Medical codes -------------------------------------------------------
# CPT: the phase prompt's `9xxxx|0xxxx` misses the 10000-89999 surgical/medical
# range (incl. 27447, used in the prompt's OWN test), so this is broadened to ANY
# 5-digit numeric. A false positive (e.g. a bare ZIP) is acceptable per the spec.
_CPT_RE = re.compile(r"\b\d{5}\b")
_HCPCS_RE = re.compile(r"\b[A-V]\d{4}\b")  # HCPCS Level II
_ICD10_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,4})?\b")
_NDC_RE = re.compile(r"\b\d{4,5}-\d{3,4}-\d{1,2}\b")

# --- 3. Identifiers ---------------------------------------------------------
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Member-ID-like: an alpha prefix followed by a long digit run (UHC/Anthem/BCBS
# member IDs commonly take this shape). Case-sensitive uppercase to avoid eating
# ordinary lowercase words.
_MEMBER_ID_RE = re.compile(r"\b[A-Z]{2,5}\d{6,12}\b")
_MRN_RE = re.compile(r"\bMRN[:\s]*\w{5,}\b", re.IGNORECASE)
_ACCT_RE = re.compile(r"\bACCT[:\s]*\w{5,}\b", re.IGNORECASE)
_CLAIM_RE = re.compile(r"\bCLAIM[:\s#]*\w{5,}\b", re.IGNORECASE)

# --- 4. PHI-suggesting phrases (case-insensitive substring) -----------------
_PHRASES = (
    "your bill",
    "your claim",
    "your diagnosis",
    "your prescription",
    "your procedure",
    "you owe",
    "your balance",
    "your eob",
    "explanation of benefits",
    "your deductible",
    "your out-of-pocket",
    "your payment of $",
    "amount due",
    "your encounter",
    "your visit on",
)

# --- 5. Diagnosis / clinical terminology (case-insensitive substring) -------
_DIAGNOSIS_TERMS = (
    "cancer",
    "diabetes",
    "depression",
    "anxiety",
    "pregnancy",
    "hiv",
    "fracture",
    "surgery on",
    "procedure on",
    "test results",
    "lab results",
)


def _context(text: str, start: int, end: int) -> str:
    lo = max(0, start - _CONTEXT)
    hi = min(len(text), end + _CONTEXT)
    return text[lo:hi].replace("\n", " ").strip()


def _scan(
    text: str, pattern: re.Pattern[str], ptype: str, confidence: str, out: list[PhiMatch]
) -> None:
    for m in pattern.finditer(text):
        out.append(PhiMatch(ptype, m.group(0), _context(text, m.start(), m.end()), confidence))


def detect_phi(text: str) -> list[PhiMatch]:
    """Return every PHI-resembling signal in ``text``. Empty list == clean.

    Coarse by design: tuned for zero false negatives, tolerant of false
    positives (which simply force the caller onto an allowlisted template).
    """
    if not text:
        return []
    matches: list[PhiMatch] = []
    low = text.lower()

    # 1. dollar amount near a medical keyword
    for m in _DOLLAR_RE.finditer(text):
        lo = max(0, m.start() - _MONEY_WINDOW)
        hi = min(len(text), m.end() + _MONEY_WINDOW)
        window = low[lo:hi]
        if any(kw in window for kw in _MEDICAL_MONEY_KEYWORDS):
            matches.append(
                PhiMatch(
                    "dollar_medical_context", m.group(0), _context(text, m.start(), m.end()), "high"
                )
            )

    # 2. medical codes
    _scan(text, _CPT_RE, "cpt_code", "medium", matches)
    _scan(text, _HCPCS_RE, "hcpcs_code", "medium", matches)
    _scan(text, _ICD10_RE, "icd10_code", "low", matches)
    _scan(text, _NDC_RE, "ndc_code", "medium", matches)

    # 3. identifiers
    _scan(text, _SSN_RE, "ssn", "high", matches)
    _scan(text, _MEMBER_ID_RE, "member_id", "medium", matches)
    _scan(text, _MRN_RE, "mrn", "high", matches)
    _scan(text, _ACCT_RE, "account_number", "high", matches)
    _scan(text, _CLAIM_RE, "claim_number", "high", matches)

    # 4. PHI-suggesting phrases
    for phrase in _PHRASES:
        idx = low.find(phrase)
        if idx != -1:
            matches.append(
                PhiMatch("phi_phrase", phrase, _context(text, idx, idx + len(phrase)), "high")
            )

    # 5. diagnosis / clinical terminology
    for term in _DIAGNOSIS_TERMS:
        idx = low.find(term)
        if idx != -1:
            matches.append(
                PhiMatch("diagnosis_term", term, _context(text, idx, idx + len(term)), "high")
            )

    return matches
