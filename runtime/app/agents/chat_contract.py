"""Freeform-chat response contract validator (Brock's 2026-08-22 field test).

The welcome-summary precedent (app/agents/greeting.passes_guardrails): a pure, regex-level
validator the evals and tests can run over any sampled response. The mode prompt carries
the contract in words (prompts/chat_modes/freeform_mode.md); this is the machine check
that catches drift — the "super long" answer and the pipe table Brock hit.

Runtime use is OBSERVATIONAL: _real_stream counts violations into DOCTRINE_VIOLATIONS
(``freeform_contract:<reason>``) and logs them. Nothing is blocked or rewritten — the
response already shipped to the user by the time it can be measured; the counters make
the drift visible on the admin System page and the evals fail on it.
"""

from __future__ import annotations

import re

# ~200 words: the contract says ≤120 by default; the eval fails at the point where even
# an "explain in detail" answer has clearly stopped being mobile-first.
MAX_WORDS_EVAL = 200
MAX_LIST_ITEMS = 4
MAX_QUESTIONS = 1

_TABLE_RE = re.compile(r"\|\s*:?-{2,}|^\s*\|.*\|\s*$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+\S", re.MULTILINE)
_STAT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")
_ERROR_CLAIM_RE = re.compile(
    r"\b(error|errors|overcharg\w*|incorrect|mistake|mistakes|wrong|inaccura\w*|billing problems?)\b",
    re.IGNORECASE,
)


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _list_blocks(text: str) -> list[int]:
    """Item counts per contiguous list block."""
    blocks: list[int] = []
    run = 0
    for line in (text or "").splitlines():
        if _LIST_ITEM_RE.match(line):
            run += 1
        elif run:
            blocks.append(run)
            run = 0
    if run:
        blocks.append(run)
    return blocks


def freeform_contract_violations(text: str) -> list[str]:
    """Reasons the text breaks the mobile-first contract; [] when it complies.

    over_length       > MAX_WORDS_EVAL words
    table             pipe-table syntax present (``|---`` or ``| a | b |`` rows)
    multiple_lists    more than one list block
    list_too_long     a list with more than MAX_LIST_ITEMS items
    multiple_questions  more than MAX_QUESTIONS question marks
    """
    reasons: list[str] = []
    if word_count(text) > MAX_WORDS_EVAL:
        reasons.append("over_length")
    if _TABLE_RE.search(text or ""):
        reasons.append("table")
    blocks = _list_blocks(text)
    if len(blocks) > 1:
        reasons.append("multiple_lists")
    if any(n > MAX_LIST_ITEMS for n in blocks):
        reasons.append("list_too_long")
    if (text or "").count("?") > MAX_QUESTIONS:
        reasons.append("multiple_questions")
    return reasons


def unsubstantiated_stat_in_tier_a(chunks: list[dict]) -> list[str]:
    """Item 5: a percentage/statistic co-occurring with an error/overcharge claim inside a
    TIER-A chunk (no citation) — the "error rates as high as 80%" pattern delivered as fact.
    Returns the offending chunk texts (truncated). A tier-B chunk with a citation may carry
    the number; tier A may not."""
    hits: list[str] = []
    for ch in chunks or []:
        if not isinstance(ch, dict) or ch.get("tier") != "A":
            continue
        text = str(ch.get("text") or "")
        if _STAT_RE.search(text) and _ERROR_CLAIM_RE.search(text):
            hits.append(text[:120])
    return hits
