"""Freeform-chat output shaping (Brock's 2026-08-22 field test).

Pure text helpers applied to the assembled assistant text BEFORE it is split into
tiered chunks and persisted:

  strip_markdown_tables   Belt-and-suspenders for the mode prompt's "never emit tables"
                          rule. The mobile renderer supports only bold/italic/lists/
                          paragraphs; a pipe table would reach the user as raw
                          ``| a | b |`` / ``|---|---|`` text. Rows become plain lines.

  extract_suggested_replies
                          The lightweight structured convention for tap-to-reply chips:
                          the model ends its answer with ONE line
                          ``SUGGESTED: ["Yes, I have a bill", "No bill yet"]``. The line
                          is parsed and STRIPPED here so it never renders; malformed
                          lines are stripped too (the raw convention must never reach a
                          user) and simply yield no chips.

  extract_directives      Both control lines (SUGGESTED / CTA), found ANYWHERE in the
                          message (e2e 2026-09-23 B3: the model put SUGGESTED above the
                          disclaimer footer and wrapped CTA in a ``` fence, and the
                          tail-only parsers rendered both as text). The last occurrence
                          wins; backticks / code fences around a control line are
                          stripped with it; whatever prose follows (the footer) stays.

  scrub_control_lines     The validator: a persisted assistant message must never
                          contain a raw ``SUGGESTED:`` / ``CTA:`` line. Anything the
                          extractor could not honour is stripped here and REPORTED so
                          the caller logs it (and the eval fails on it).
"""

from __future__ import annotations

import json
import re

MAX_SUGGESTED = 4
MAX_SUGGESTED_WORDS = 5

# The create-case call to action (2026-08-22, case-intent fix). The model emits a final
# ``CTA: create_case`` line — the SAME trailing-directive family as SUGGESTED — and the
# server attaches this action to the turn's citations so CreateCaseCta renders a button.
CREATE_CASE_CTA: dict = {"action_type": "create_case_cta", "title": "Create a case"}
KNOWN_CTAS: dict[str, dict] = {"create_case": CREATE_CASE_CTA}
_CTA_LINE_RE = re.compile(r"^\s*CTA\s*:\s*([A-Za-z_]+)\s*$", re.IGNORECASE)

_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_SUGGESTED_LINE_RE = re.compile(r"^\s*SUGGESTED\s*:\s*(.*?)\s*$", re.IGNORECASE)
# A control line with the decoration the model tends to add: inline backticks, a same-line
# fence (```CTA: create_case```), bold, a trailing period.
_DECORATED_LINE_RE = re.compile(
    r"^\s*(?:`{1,3}\s*\w*\s*)?(?:\*\*)?\s*(SUGGESTED|CTA)\s*:\s*(.*?)\s*(?:\*\*)?\s*`{0,3}\s*\.?\s*$",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^\s*`{3,}\s*\w*\s*$")
_CONTROL_TOKEN_RE = re.compile(r"(?im)^\W{0,8}(SUGGESTED|CTA)\s*:")


def strip_markdown_tables(text: str) -> str:
    """Convert pipe-table rows to plain lines; drop separator rows. Non-table text is
    returned byte-identical."""
    if not text or "|" not in text:
        return text
    out: list[str] = []
    for line in text.splitlines():
        if _TABLE_SEP_RE.match(line) and "-" in line:
            continue  # |---|---| row: pure syntax, nothing to say
        if _TABLE_ROW_RE.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                out.append(" — ".join(cells))
            continue
        out.append(line)
    return "\n".join(out)


def _clean_reply(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    s = " ".join(value.split())
    if not s or len(s.split()) > MAX_SUGGESTED_WORDS or len(s) > 60:
        return None
    return s


def extract_suggested_replies(text: str) -> tuple[str, list[str]]:
    """Return (text_without_the_SUGGESTED_line, replies).

    Only a SUGGESTED line at the END of the text (trailing whitespace allowed) is honored;
    one mid-text would be model confusion and is left alone as ordinary text. A malformed
    payload (not a JSON array of strings) is stripped and yields []. Items over
    MAX_SUGGESTED are dropped, and any item longer than MAX_SUGGESTED_WORDS words is
    skipped — chips are for small closed choices, not sentences.
    """
    if not text:
        return text, []
    lines = text.rstrip().splitlines()
    if not lines:
        return text, []
    m = _SUGGESTED_LINE_RE.match(lines[-1])
    if not m:
        return text, []
    stripped = "\n".join(lines[:-1]).rstrip()
    raw = m.group(1)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return stripped, []
    if not isinstance(parsed, list):
        return stripped, []
    replies: list[str] = []
    for item in parsed:
        cleaned = _clean_reply(item)
        if cleaned and cleaned not in replies:
            replies.append(cleaned)
        if len(replies) >= MAX_SUGGESTED:
            break
    return stripped, replies


def _parse_suggested(raw: str) -> list[str] | None:
    """The chip list from a SUGGESTED payload, or None when it is not a JSON array of
    strings (a malformed line is still a control line — stripped, never rendered)."""
    raw = raw.strip().strip("`").strip()
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(parsed, list):
        return None
    replies: list[str] = []
    for item in parsed:
        cleaned = _clean_reply(item)
        if cleaned and cleaned not in replies:
            replies.append(cleaned)
        if len(replies) >= MAX_SUGGESTED:
            break
    return replies


def _tidy(lines: list[str]) -> str:
    """Drop fences left empty by a removed control line, collapse runs of blank lines."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        if _FENCE_RE.match(lines[i]):
            # a fence whose body is now empty (or only blank lines) closes on the next fence
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _FENCE_RE.match(lines[j]):
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_directives(text: str) -> tuple[str, list[str], str | None]:
    """Find EVERY control line — ``SUGGESTED: [...]`` (tap-to-reply chips) and
    ``CTA: create_case`` (the create-case button) — anywhere in the text, in any order,
    with or without backticks / a code fence around them, with prose (the disclaimer
    footer) after them. Returns (clean_text, suggested_replies, cta_name). The LAST
    occurrence of each wins. A CTA naming an unknown action is stripped and ignored; a
    malformed SUGGESTED line is stripped and yields no chips. Directives never render."""
    lines = (text or "").splitlines()
    kept: list[str] = []
    replies: list[str] = []
    cta: str | None = None
    for line in lines:
        m = _DECORATED_LINE_RE.match(line)
        if not m:
            kept.append(line)
            continue
        kind, payload = m.group(1).upper(), m.group(2)
        if kind == "SUGGESTED":
            found = _parse_suggested(payload)
            if found is not None:
                replies = found  # last occurrence wins; a malformed line changes nothing
        else:
            name = payload.strip().strip("`").strip().rstrip(".").lower()
            if name in KNOWN_CTAS:
                cta = name  # last occurrence wins
    return _tidy(kept), replies, cta


def scrub_control_lines(text: str) -> tuple[str, list[str]]:
    """The validator (belt AND braces): any line that still starts with ``SUGGESTED:`` or
    ``CTA:`` after extraction is removed, and the kinds found are returned so the caller
    can log the leak. A persisted assistant message never carries the raw convention."""
    found: list[str] = []
    kept: list[str] = []
    for line in (text or "").splitlines():
        m = _CONTROL_TOKEN_RE.match(line)
        if m:
            found.append(m.group(1).upper())
            continue
        kept.append(line)
    if not found:
        return text or "", []
    return _tidy(kept), found


def has_raw_control_line(text: str) -> bool:
    return bool(_CONTROL_TOKEN_RE.search(text or ""))
