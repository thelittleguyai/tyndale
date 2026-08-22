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


def extract_directives(text: str) -> tuple[str, list[str], str | None]:
    """Peel EVERY trailing directive line off the text, in any order:
    ``SUGGESTED: [...]`` (tap-to-reply chips) and ``CTA: create_case`` (the create-case
    button). Returns (clean_text, suggested_replies, cta_name). A CTA line naming an
    unknown action is stripped and ignored; a malformed SUGGESTED line is stripped and
    yields no chips. Directives never render as text."""
    current = text or ""
    replies: list[str] = []
    cta: str | None = None
    for _ in range(4):  # bounded: at most a couple of directive lines
        lines = current.rstrip().splitlines()
        if not lines:
            break
        last = lines[-1]
        if _SUGGESTED_LINE_RE.match(last):
            current, found = extract_suggested_replies(current)
            if found and not replies:
                replies = found
            continue
        m = _CTA_LINE_RE.match(last)
        if m:
            current = "\n".join(lines[:-1]).rstrip()
            name = m.group(1).strip().lower()
            if name in KNOWN_CTAS and cta is None:
                cta = name
            continue
        break
    return current, replies, cta
