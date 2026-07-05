"""Medicare Advantage (Part C) EOB parser (Sprint E wave 1).

Follows the CMS model EOB template: per-service claim rows plus a maximum-out-of-pocket
(MOOP) tracker. Emits the normalized EOB shape the accumulator consumes, mapping the
member's cost-share to the OOP-applied field and the MOOP paid-to-date to the stated YTD, so
the Independent Audit can reconstruct the MOOP progress. Defensive + per-field confidence;
never fabricates a figure.
"""

from __future__ import annotations

import re
import typing

from app.sources.parsers._common import date_after, money, money_after, text_after

if typing.TYPE_CHECKING:
    from app.sources.parsers import ParsedDocument

_CLAIM_SPLIT = re.compile(r"(?=claim\s*(?:number|no\.?|#)\s*[:#])", re.IGNORECASE)
# "You have paid $1,200.00 of your $8,300.00 out-of-pocket maximum"
_MOOP_RE = re.compile(
    r"paid\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*of\s*your\s*\$\s*[\d,]+(?:\.\d{1,2})?[^.\n]*"
    r"out[- ]of[- ]pocket",
    re.IGNORECASE,
)


def _claim_from_block(block: str, oop_ytd: float | None) -> dict | None:
    responsibility = money_after(
        block, "Your responsibility", "Amount you may be billed", "Your cost",
        "Member responsibility", "You owe",
    )
    billed = money_after(block, "Amount charged", "Provider charged", "Amount Charged", "Billed")
    approved = money_after(block, "Plan approved", "Plan Approved", "Allowed amount", "Medicare-approved")
    plan_paid = money_after(block, "Plan paid", "Amount plan paid", "Plan Paid")
    oop_applied = money_after(
        block, "Applied to your out-of-pocket", "Applied to out-of-pocket",
        "Applied to your maximum out-of-pocket",
    )
    dos = date_after(block, "Date of service", "Dates of service", "Service date")
    processed = date_after(block, "Date processed", "Processed on", "Claim processed", "Adjudicated")
    provider = text_after(block, "Provider:")

    if responsibility is None and billed is None and dos is None:
        return None

    eob = {
        "claim_id": text_after(block, "Claim number", "Claim Number", "Claim No"),
        "billed_amount": billed,
        "allowed_amount": approved,
        "patient_responsibility": responsibility,
        "date_of_service": dos,
        "adjudication_date": processed,
        "amount_applied_to_deductible": None,
        # MA cost-share counts toward the MOOP; use the explicit line, else the member's
        # responsibility for the covered service (both left None when absent).
        "amount_applied_to_oop": oop_applied if oop_applied is not None else responsibility,
        "deductible_ytd_stated": None,
        "oop_ytd_stated": oop_ytd,
        "network_status": None,
        "remark_codes": [],
        "plan_paid": plan_paid,
        "provider": provider,
    }
    confidence = {
        k: 0.7
        for k in (
            "patient_responsibility", "billed_amount", "allowed_amount", "date_of_service",
            "adjudication_date", "amount_applied_to_oop", "plan_paid", "provider",
        )
        if eob.get(k) is not None
    }
    return {"eob": eob, "source_type": "ma_eob", "field_confidence": confidence}


def parse_ma_eob(text: str) -> ParsedDocument:
    from app.sources.parsers import ParsedDocument

    text = text or ""
    moop_match = _MOOP_RE.search(text)
    oop_ytd = money(f"${moop_match.group(1)}") if moop_match else None

    blocks = [b for b in _CLAIM_SPLIT.split(text) if "claim" in b.lower()]
    if not blocks:
        blocks = [text]  # single-claim EOB with no explicit claim-number markers
    claims = [c for b in blocks if (c := _claim_from_block(b, oop_ytd))]

    assumptions = [
        "Medicare Advantage EOB parsed heuristically from OCR text; member cost-share is "
        "mapped to the MOOP-applied field for the accumulator reconstruction.",
    ]
    if not claims:
        assumptions.append("no claims could be parsed from this MA EOB — layout unrecognized")

    anchored = any(c["eob"].get("patient_responsibility") is not None for c in claims)
    provenance = {
        "adapter": "MAEOBExtractor",
        "source_kind": "user_upload",
        "confidence": 0.6 if anchored else 0.3,
        "assumptions": assumptions,
    }
    return ParsedDocument(
        source_type="ma_eob",
        regime_implied="medicare_advantage",
        claims=claims,
        provenance=provenance,
        assumptions=assumptions,
    )
