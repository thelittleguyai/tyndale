"""Data-quality detection — the signals behind Brock's §5.1 and §5.2 copy (F3 / F4).

His strings were authored and sat unused because nothing detected the CONDITIONS they describe.
Both detectors are deterministic and conservative: they only fire on positive evidence, because
a false "this is unreadable" is as bad as missing a real one.

  partial_read()      §5.1 — some of the document read, some didn't. The point is what we do
                      NEXT: run what IS readable, name the unreadable part specifically, and
                      ask for the one fix — and NEVER print an approximate number. A partially
                      recovered figure is exactly the case where guessing is most tempting and
                      most damaging, so a partial value is discarded, not rounded.

  looks_like_summary_bill()
                      §5.2 — a bill carrying charges but no line-item CPT detail (the Beloit
                      shape): a summary statement. Errors hide in the itemised version, so this
                      coaches the user to request it rather than auditing a total.
"""

from __future__ import annotations

import re
from typing import Any

# A charge line on an itemised bill: a CPT/HCPCS code near a dollar amount.
_CPT_RE = re.compile(r"\b\d{5}\b|\b[A-Z]\d{4}\b")
_MONEY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
# Summary statements say this about themselves; itemised ones say the opposite.
_SUMMARY_MARKERS = (
    "SUMMARY OF CHARGES", "STATEMENT SUMMARY", "ACCOUNT SUMMARY", "BALANCE FORWARD",
    "TOTAL CHARGES", "AMOUNT DUE", "PLEASE PAY THIS AMOUNT",
)
_ITEMIZED_MARKERS = (
    "ITEMIZED", "LINE ITEM", "DETAIL OF CHARGES", "CPT", "HCPCS", "REVENUE CODE", "PROCEDURE CODE",
)

# Below this, a "read" document didn't really read — the OCR returned a fragment.
_MIN_USABLE_CHARS = 120


def _doc(d: Any, key: str, default=None):
    return d.get(key, default) if isinstance(d, dict) else getattr(d, key, default)


def partial_read(documents: Any) -> dict | None:
    """§5.1 — ``{"readable": [...], "unreadable": [...], "unreadable_label": str}`` when SOME
    documents read and others didn't, else None.

    Deliberately NOT fired when everything failed (that is the existing extraction_failed
    state) or when everything read — §5.1 is specifically the mixed case, where Tyndale can
    still deliver value on part of the upload."""
    docs = [d for d in (documents or [])]
    if len(docs) < 1:
        return None
    readable, unreadable = [], []
    for d in docs:
        status = _doc(d, "extraction_status") or "unknown"
        chars = int(_doc(d, "ocr_text_chars", 0) or 0)
        name = _doc(d, "filename") or "a document"
        (readable if status == "extracted" and chars >= _MIN_USABLE_CHARS else unreadable).append(name)
    if not readable or not unreadable:
        return None  # all-good or all-failed — neither is the §5.1 state
    return {
        "readable": readable,
        "unreadable": unreadable,
        # Names the unreadable part SPECIFICALLY (his §5.1 asks for one precise fix).
        "unreadable_label": unreadable[0] if len(unreadable) == 1 else f"{len(unreadable)} of your files",
    }


def looks_like_summary_bill(document: Any) -> bool:
    """§5.2 — a bill with charges but no line-item detail (the Beloit shape).

    Requires positive evidence on BOTH sides: money present, and itemisation absent. A bill we
    simply read badly is not a summary bill — that is §5.1's case, not this one."""
    if (_doc(document, "document_type") or "") not in ("bill", "itemized_bill", "collections_notice"):
        return False
    text = (_doc(document, "ocr_text_preview") or "").upper()
    if len(text) < _MIN_USABLE_CHARS:
        return False  # too little read to claim anything about its structure
    if any(m in text for m in _ITEMIZED_MARKERS):
        return False  # it says it IS itemised
    if not _MONEY_RE.search(text):
        return False  # no charges at all — nothing to summarise
    # An itemised bill has several code+money rows; a summary has a total and little else.
    return len(_CPT_RE.findall(text)) < 2 and any(m in text for m in _SUMMARY_MARKERS)


def never_approximate(value: Any) -> None:
    """A partially-recovered figure is DISCARDED, never rounded into the user's copy.

    Kept as an explicit, named no-op so the intent is greppable and testable: §5.1's whole
    point is "I won't guess at a number on your bill", and the failure mode it guards against
    is a half-read total silently becoming an authoritative one."""
    return None
