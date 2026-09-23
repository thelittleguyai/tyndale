"""User-facing finding prose hygiene (e2e 2026-09-23 minors).

Two things the results page showed that a user should never read in a finding:

  * analyst-speak — "Legal claim is contingent on OOP max verification — omitted from primary
    finding until confirmed" is the agent talking to itself; the user gets one registry line
    saying the same thing in Tyndale's voice, or nothing;
  * the account holder's own full name interpolated into the prose ("Phil Fluegel was billed…")
    — the finding is addressed to the user, so it says "you".

Both are pure string passes applied at PROJECTION (`_assemble_result`), never to the stored
rows — the reviewer's provenance tab keeps the agent's exact words.
"""

from __future__ import annotations

import re
from typing import Any

# One sentence that reads as analyst bookkeeping rather than a fact for the user.
_ANALYST_RE = re.compile(
    r"(?i)\b(omitted from (?:the )?(?:primary )?finding|until (?:it is |it's )?confirmed|"
    r"contingent on [^.;]* verification|pending verification|flagged for (?:internal )?review|"
    r"not (?:yet )?surfaced to the user|internal note|for the record)\b"
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def scrub_analyst_speak(text: str, replacement: str | None) -> tuple[str, bool]:
    """Drop the sentences that talk to the analyst. If NOTHING is left, the registry line
    (``replacement``) stands in — or an empty string when there is no line to give."""
    if not isinstance(text, str) or not text.strip():
        return text, False
    parts = _SENTENCE_SPLIT.split(text.strip())
    kept = [s for s in parts if not _ANALYST_RE.search(s)]
    if len(kept) == len(parts):
        return text, False
    out = " ".join(kept).strip()
    return (out or (replacement or "")), True


def _name_pattern(first: str | None, last: str | None) -> re.Pattern | None:
    first, last = (first or "").strip(), (last or "").strip()
    if not first or not last:
        return None
    return re.compile(rf"\b{re.escape(first)}\s+(?:[A-Z]\.?\s+)?{re.escape(last)}\b", re.IGNORECASE)


# After the name becomes "you", the verb that followed a third-person subject agrees again.
_AGREEMENT = [(re.compile(rf"\byou {a}\b", re.IGNORECASE), f"you {b}") for a, b in (
    ("was", "were"), ("is", "are"), ("has", "have"), ("owes", "owe"), ("pays", "pay"), ("does", "do"),
    ("wasn't", "weren't"), ("isn't", "aren't"), ("hasn't", "haven't"), ("doesn't", "don't"),
)]


def replace_account_holder(text: str, first: str | None, last: str | None) -> str:
    """The account holder's full name becomes "you" (possessive → "your"), and the verb that
    followed it agrees again ("you were billed", "you owe"). A finding addresses the user."""
    pat = _name_pattern(first, last)
    if pat is None or not isinstance(text, str):
        return text
    text = re.sub(rf"{pat.pattern}[’']s\b", "your", text, flags=re.IGNORECASE)
    text = pat.sub("you", text)
    for rx, fix in _AGREEMENT:
        text = rx.sub(fix, text)
    # a sentence that now STARTS with "you" / "your" keeps sentence case
    return re.sub(r"(^|[.!?]\s+)(you|your)\b", lambda m: m.group(1) + m.group(2).capitalize(), text)


def clean_finding_payloads(
    facts: dict | None, legal_claim: dict | None, recommendation: dict | None,
    *, first_name: str | None, last_name: str | None, pending_line: str | None,
) -> tuple[dict, dict | None, dict | None, bool]:
    """Apply both passes to every user-facing string in the three payloads. Returns the
    cleaned copies and whether any analyst sentence was removed."""
    hit = False

    def clean(node: Any):
        nonlocal hit
        if isinstance(node, dict):
            return {k: clean(v) for k, v in node.items()}
        if isinstance(node, list):
            return [clean(v) for v in node]
        if isinstance(node, str):
            s, h = scrub_analyst_speak(node, pending_line)
            hit = hit or h
            return replace_account_holder(s, first_name, last_name)
        return node

    return clean(facts or {}), clean(legal_claim) if legal_claim else legal_claim, clean(recommendation) if recommendation else recommendation, hit
