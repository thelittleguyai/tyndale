"""Insurance-card + SBC field extraction for the intake wizard (Phase CO-1A).

Deterministic, confidence-scored heuristic extraction over OCR text. Each field
carries a confidence in [0,1]:
  - strong labeled match  → 0.92
  - weak/unlabeled match  → 0.60   (< 0.85 → trivial yes/no confirmation, P1)
  - not found             → 0.00   (absent; handled by manual entry, not a prompt)

The `*_from_text` functions are pure (fixture-testable, no OCR/Claude). The async
`extract_*` wrappers load a document's OCR text (running the existing bill_ocr_extract
tool / stub when text isn't already stored) and reuse the pure path.

High-confidence fields are persisted to case_files.coverage via the dedicated
pg_store_* tools (DL-39). DL-54: insurance cards carry no CPT descriptors; SBC
extraction stores plan terms + code-free category labels only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STRONG = 0.92
_WEAK = 0.60
_NONE = 0.0
_CONFIRM_THRESHOLD = 0.85

_KNOWN_PAYERS = (
    "unitedhealthcare",
    "united healthcare",
    "uhc",
    "aetna",
    "cigna",
    "anthem",
    "elevance",
    "blue cross",
    "blue shield",
    "bcbs",
    "humana",
    "kaiser",
    "centene",
    "wellcare",
    "molina",
)


@dataclass
class FieldValue:
    value: str | float | None
    confidence: float


@dataclass
class InsuranceCardFields:
    payer: FieldValue
    member_id: FieldValue
    group_number: FieldValue
    plan_name: FieldValue

    def items(self) -> dict[str, FieldValue]:
        return {
            "payer": self.payer,
            "member_id": self.member_id,
            "group_number": self.group_number,
            "plan_name": self.plan_name,
        }

    def confirmations(self, threshold: float = _CONFIRM_THRESHOLD) -> list[dict]:
        """Fields found but below confidence → trivial yes/no confirmation prompts."""
        out: list[dict] = []
        labels = {
            "payer": "insurer",
            "member_id": "member ID",
            "group_number": "group number",
            "plan_name": "plan name",
        }
        for key, fv in self.items().items():
            if fv.value is not None and fv.confidence < threshold:
                out.append(
                    {
                        "field": key,
                        "read_value": str(fv.value),
                        "prompt": f"I read your {labels[key]} as '{fv.value}' — does that match your card?",
                        "confidence": fv.confidence,
                    }
                )
        return out

    def high_confidence_coverage(self, threshold: float = _CONFIRM_THRESHOLD) -> dict:
        """Coverage-JSONB fields confident enough to persist silently."""
        out: dict = {}
        coverage_key = {
            "payer": "payer_name",
            "member_id": "member_id",
            "group_number": "group_number",
            "plan_name": "plan_name",
        }
        for key, fv in self.items().items():
            if fv.value is not None and fv.confidence >= threshold:
                out[coverage_key[key]] = fv.value
        return out


@dataclass
class SBCFields:
    deductible_individual: FieldValue
    deductible_family: FieldValue
    oop_max_individual: FieldValue
    oop_max_family: FieldValue
    coinsurance_in_network: FieldValue
    coinsurance_out_of_network: FieldValue
    copay_pcp: FieldValue
    copay_specialist: FieldValue
    copay_er: FieldValue
    copay_urgent_care: FieldValue
    prior_auth_required_categories: list[str] = field(default_factory=list)

    def high_confidence_coverage(self, threshold: float = _CONFIRM_THRESHOLD) -> dict:
        m = {
            "deductible_individual": "deductible_amount",
            "oop_max_individual": "oop_max_amount",
            "coinsurance_in_network": "coinsurance_percent",
            "copay_pcp": "copay_pcp",
            "copay_specialist": "copay_specialist",
            "copay_er": "copay_er",
            "copay_urgent_care": "copay_urgent_care",
        }
        out: dict = {}
        for attr, ckey in m.items():
            fv: FieldValue = getattr(self, attr)
            if fv.value is not None and fv.confidence >= threshold:
                out[ckey] = fv.value
        # families + OON stored under explicit keys when present
        for attr, ckey in (
            ("deductible_family", "deductible_family"),
            ("oop_max_family", "oop_max_family"),
            ("coinsurance_out_of_network", "coinsurance_out_of_network"),
        ):
            fv = getattr(self, attr)
            if fv.value is not None and fv.confidence >= threshold:
                out[ckey] = fv.value
        if self.prior_auth_required_categories:
            out["prior_auth_required_categories"] = list(self.prior_auth_required_categories)
        return out


# --------------------------------------------------------------------------- #
# Pure text extraction
# --------------------------------------------------------------------------- #
def _money(text: str) -> float | None:
    m = re.search(r"\$\s?([\d,]+(?:\.\d{2})?)", text)
    return float(m.group(1).replace(",", "")) if m else None


def _labeled(text: str, label_rx: str) -> tuple[str, float] | None:
    m = re.search(label_rx, text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), _STRONG
    return None


def extract_insurance_card_from_text(text: str) -> InsuranceCardFields:
    t = text or ""

    # payer — known names are high confidence; otherwise the first non-empty line is a weak guess
    payer_fv = FieldValue(None, _NONE)
    low = t.lower()
    for name in _KNOWN_PAYERS:
        if name in low:
            idx = low.index(name)
            payer_fv = FieldValue(t[idx : idx + len(name)], _STRONG)
            break
    else:
        first = next((ln.strip() for ln in t.splitlines() if ln.strip()), "")
        if first:
            payer_fv = FieldValue(first, _WEAK)

    # member id — "Member ID: X" strong; bare "ID X" weak
    member_fv = FieldValue(None, _NONE)
    strong = _labeled(t, r"member\s*(?:id|#|no\.?)\s*[:#]?\s*([A-Z0-9][A-Z0-9\- ]{4,})")
    if strong:
        member_fv = FieldValue(strong[0].strip(), _STRONG)
    else:
        weak = re.search(r"\bID[:#]?\s*([A-Z0-9]{6,})", t)
        if weak:
            member_fv = FieldValue(weak.group(1), _WEAK)

    # group number
    group_fv = FieldValue(None, _NONE)
    g = _labeled(t, r"group\s*(?:number|#|no\.?)?\s*[:#]?\s*([A-Z0-9\-]{3,})")
    if g:
        group_fv = FieldValue(g[0], _STRONG)

    # plan name
    plan_fv = FieldValue(None, _NONE)
    p = _labeled(t, r"plan(?:\s*name)?\s*[:#]\s*(.+)")
    if p:
        plan_fv = FieldValue(p[0].splitlines()[0].strip(), _STRONG)

    return InsuranceCardFields(payer_fv, member_fv, group_fv, plan_fv)


def _dollar_after(text: str, label_rx: str) -> FieldValue:
    # label_rx MUST be wrapped non-capturing: with an alternation label ("a|b|c") the bare
    # concatenation bound the amount suffix to the LAST alternative only, so text matching an
    # earlier alternative ("Deductible individual" with no $ in reach) matched with group(1)
    # = None and CRASHED extraction (found 2026-08-19 wiring the plan-level SBC home).
    m = re.search(
        r"(?:" + label_rx + r")[^\$]{0,40}\$\s?([\d,]+(?:\.\d{2})?)", text, re.IGNORECASE
    )
    if m:
        return FieldValue(float(m.group(1).replace(",", "")), _STRONG)
    return FieldValue(None, _NONE)


def _percent_after(text: str, label_rx: str) -> FieldValue:
    m = re.search(r"(?:" + label_rx + r")[^\d]{0,40}(\d{1,3})\s*%", text, re.IGNORECASE)
    if m:
        return FieldValue(float(m.group(1)), _STRONG)
    return FieldValue(None, _NONE)


def extract_sbc_from_text(text: str) -> SBCFields:
    t = text or ""
    cats: list[str] = []
    for cat in (
        "imaging",
        "mri",
        "ct",
        "surgery",
        "inpatient",
        "specialty drug",
        "physical therapy",
    ):
        if re.search(rf"{cat}[^.]{{0,60}}prior auth", t, re.IGNORECASE) or re.search(
            rf"prior auth[^.]{{0,60}}{cat}", t, re.IGNORECASE
        ):
            cats.append(cat)
    return SBCFields(
        deductible_individual=_dollar_after(
            t, r"deductible[^\n]*?individual|individual[^\n]*?deductible|deductible"
        ),
        deductible_family=_dollar_after(t, r"family[^\n]*?deductible|deductible[^\n]*?family"),
        oop_max_individual=_dollar_after(t, r"out[\- ]of[\- ]pocket[^\n]*?(?:max|limit)"),
        oop_max_family=_dollar_after(t, r"family[^\n]*?out[\- ]of[\- ]pocket"),
        coinsurance_in_network=_percent_after(t, r"coinsurance"),
        coinsurance_out_of_network=FieldValue(None, _NONE),
        copay_pcp=_dollar_after(t, r"primary care|pcp|primary"),
        copay_specialist=_dollar_after(t, r"specialist"),
        copay_er=_dollar_after(t, r"emergency"),
        copay_urgent_care=_dollar_after(t, r"urgent care"),
        prior_auth_required_categories=cats,
    )


# --------------------------------------------------------------------------- #
# Async wrappers (load a stored document's OCR text, then extract)
# --------------------------------------------------------------------------- #
async def _ocr_text_for(document: dict) -> str:
    """OCR text for a stored document dict (case_files.documents entry).

    Uses any already-stored ocr_text; otherwise runs the existing bill_ocr_extract
    tool (real Azure DI when use_real_ocr, else the keyword stub)."""
    if document.get("ocr_text"):
        return str(document["ocr_text"])
    from app.tools import call_tool

    args = {"filename": document.get("filename", "")}
    if document.get("content_base64"):
        args["content_base64"] = document["content_base64"]
    elif document.get("file_path"):
        args["file_path"] = document["file_path"]
    try:
        result = await call_tool("bill_ocr_extract", args)
        return str(result.get("ocr_text", ""))
    except Exception:  # noqa: BLE001 — extraction must degrade, never hard-fail intake
        return ""


def _find_document(documents: list[dict], document_id: str) -> dict | None:
    return next((d for d in documents if str(d.get("document_id")) == str(document_id)), None)


async def extract_insurance_card(documents: list[dict], document_id: str) -> InsuranceCardFields:
    doc = _find_document(documents, document_id) or {}
    return extract_insurance_card_from_text(await _ocr_text_for(doc))


async def extract_sbc(documents: list[dict], document_id: str) -> SBCFields:
    doc = _find_document(documents, document_id) or {}
    return extract_sbc_from_text(await _ocr_text_for(doc))
