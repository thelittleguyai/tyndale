"""Summary-bill detection (Phase CO-12C, §4 guided flow).

A deterministic heuristic over a bill's OCR text: a *summary* statement (few lines,
round-number totals, "balance forward", and crucially NO per-line CPT/HCPCS codes)
can't be audited line-by-line, so Tyndale flags it and hands the user a script to
request a fully itemized bill. It NEVER blocks — it only surfaces guidance.
"""

from __future__ import annotations

import re
from typing import Any

_CPT_RE = re.compile(r"\b\d{5}\b")  # CPT / 5-digit procedure code
_HCPCS_RE = re.compile(r"\b[A-V]\d{4}\b")  # HCPCS Level II
_DOLLAR_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")

# INTERIM engineering copy for the registry's {itemized_request_script} slot
# (dataquality_summary_not_itemized, §5.2) — wired 2026-08-27 (audit group 3) so the key
# renders complete instead of degrading; PROPOSED for Brock's rewrite in the v2 draft.
ITEMIZED_REQUEST_SCRIPT = (
    "Hi, I'm requesting a fully itemized bill for my account. The statement I received "
    "shows only a summary total. Please send an itemized statement that lists every "
    "service separately with its procedure code (CPT/HCPCS), the date of service, the "
    "charge for each line, and any payments or adjustments applied. I need the "
    "line-level detail to review the charges. Thank you."
)


def detect_summary_bill(ocr_text: str) -> dict[str, Any]:
    """Return {is_summary, reasons[], itemized_request_script|None}.

    A bill is flagged as a summary when it has NO per-line procedure codes AND shows
    at least one other summary signal (balance-forward language, only round-number
    totals, or very few lines). Heuristic + non-blocking by design."""
    text = ocr_text or ""
    upper = text.upper()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    has_codes = bool(_CPT_RE.search(text) or _HCPCS_RE.search(text))

    reasons: list[str] = []
    if "BALANCE FORWARD" in upper or "PREVIOUS BALANCE" in upper or "AMOUNT FORWARD" in upper:
        reasons.append(
            "contains 'balance forward' / 'previous balance' — a summary-statement marker"
        )

    dollars = [float(d.replace(",", "")) for d in _DOLLAR_RE.findall(text)]
    round_only = bool(dollars) and all(d.is_integer() and d % 10 == 0 for d in dollars)
    if round_only and len(dollars) <= 4:
        reasons.append("only round-number totals, no itemized per-line charges")

    if len(lines) <= 6:
        reasons.append(f"very few lines ({len(lines)}) for an itemized bill")

    if not has_codes:
        reasons.append("no CPT/HCPCS procedure codes found (itemized bills list a code per line)")

    # Summary iff no codes AND at least one corroborating signal beyond that.
    is_summary = not has_codes and len(reasons) >= 2
    return {
        "is_summary": is_summary,
        "reasons": reasons,
        "itemized_request_script": ITEMIZED_REQUEST_SCRIPT if is_summary else None,
    }
