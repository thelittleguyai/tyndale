"""Medicare Summary Notice parser (Sprint E wave 1).

An MSN is semiannual and multi-claim. The **"Maximum You May Be Billed" column is the audit
anchor** — it is the member's true ceiling, which Tyndale compares against the provider's
bill. Layout varies wildly across MSN versions, so every field is parsed defensively with
per-field confidence and is left None when not found — never fabricated.

Emits the normalized EOB shape the accumulator consumes, tagged source_type="msn", with the
MSN-specific extras (medicare_paid, provider, service, appeal_deadline) alongside.
"""

from __future__ import annotations

import re
import typing

from app.sources.parsers._common import date_after, money, money_after, text_after

if typing.TYPE_CHECKING:
    from app.sources.parsers import ParsedDocument

_CLAIM_SPLIT = re.compile(r"(?=claim\s*(?:number|no\.?|#)\s*[:#])", re.IGNORECASE)
# "You have now met $203.00 of your $240.00 ... deductible"
_DED_MET_RE = re.compile(
    r"met\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*of\s*your\s*\$\s*[\d,]+(?:\.\d{1,2})?[^.\n]*deductible",
    re.IGNORECASE,
)


def _claim_from_block(block: str, deductible_ytd: float | None, appeal_deadline: str | None) -> dict | None:
    max_billed = money_after(block, "Maximum You May Be Billed", "Maximum you may be billed")
    billed = money_after(block, "Amount Provider Charged", "Provider Charged", "Amount Charged")
    approved = money_after(block, "Medicare-Approved Amount", "Medicare Approved Amount", "Approved Amount")
    medicare_paid = money_after(block, "Amount Medicare Paid", "Medicare Paid")
    dos = date_after(block, "Date of Service", "Dates of Service", "Service Date")
    provider = text_after(block, "Provider:")
    service = text_after(block, "Service Provided", "Service:")
    claim_id = text_after(block, "Claim number", "Claim Number", "Claim No")
    ded_line = money_after(block, "Deductible", "Applied to Deductible")

    # A claim needs at least a dollar anchor or a date to be real (never fabricate a row).
    if max_billed is None and billed is None and dos is None:
        return None

    eob = {
        "claim_id": claim_id,
        "billed_amount": billed,
        "allowed_amount": approved,
        # THE ANCHOR — the Maximum You May Be Billed is the member responsibility ceiling.
        "patient_responsibility": max_billed,
        "date_of_service": dos,
        "adjudication_date": None,  # MSNs carry no per-claim adjudication date
        "amount_applied_to_deductible": ded_line,
        "amount_applied_to_oop": None,
        "deductible_ytd_stated": deductible_ytd,
        "oop_ytd_stated": None,
        "network_status": None,
        "remark_codes": [],
        # MSN-specific extras (carried for the audit; ignored by the accumulator math).
        "medicare_paid": medicare_paid,
        "provider": provider,
        "service_description": service,
        "appeal_deadline": appeal_deadline,
    }
    confidence = {
        k: 0.7
        for k in (
            "patient_responsibility", "billed_amount", "allowed_amount", "date_of_service",
            "medicare_paid", "provider", "service_description", "amount_applied_to_deductible",
        )
        if eob.get(k) is not None
    }
    return {"eob": eob, "source_type": "msn", "field_confidence": confidence}


def parse_msn(text: str) -> ParsedDocument:
    from app.sources.parsers import ParsedDocument

    text = text or ""
    ded_match = _DED_MET_RE.search(text)
    deductible_ytd = money(f"${ded_match.group(1)}") if ded_match else None
    appeal_deadline = date_after(
        text, "file your appeal by", "must be filed by", "appeal must be received by", "appeal by"
    )

    blocks = [b for b in _CLAIM_SPLIT.split(text) if "claim" in b.lower()]
    claims = [c for b in blocks if (c := _claim_from_block(b, deductible_ytd, appeal_deadline))]

    assumptions = [
        "Medicare Summary Notice parsed heuristically from OCR text; the "
        "'Maximum You May Be Billed' figure is the member-responsibility anchor.",
    ]
    if not claims:
        assumptions.append("no claims could be parsed from this MSN — layout unrecognized")

    anchored = any(c["eob"].get("patient_responsibility") is not None for c in claims)
    provenance = {
        "adapter": "MSNExtractor",
        "source_kind": "user_upload",
        "confidence": 0.6 if anchored else 0.3,
        "assumptions": assumptions,
    }
    return ParsedDocument(
        source_type="msn",
        regime_implied="medicare_traditional",
        claims=claims,
        provenance=provenance,
        assumptions=assumptions,
    )
