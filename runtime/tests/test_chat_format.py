"""Freeform-chat output shaping (Brock's 2026-08-22 field test) — pure helpers."""

from __future__ import annotations

from app.agents.chat_format import strip_markdown_tables

_TABLE = (
    "Here is a comparison:\n\n"
    "| Term | Meaning |\n"
    "|---|---|\n"
    "| Deductible | What you pay first |\n"
    "| Copay | A flat fee per visit |\n\n"
    "Hope that helps."
)


def test_tables_become_plain_lines_with_no_pipes():
    out = strip_markdown_tables(_TABLE)
    assert "|" not in out
    assert "---" not in out
    assert "Term — Meaning" in out
    assert "Deductible — What you pay first" in out
    assert out.startswith("Here is a comparison:") and out.endswith("Hope that helps.")


def test_non_table_text_is_untouched():
    plain = "A deductible is what you pay first.\n\n- one\n- two\n\nAsk me anything."
    assert strip_markdown_tables(plain) == plain
    assert strip_markdown_tables("") == ""


def test_a_lone_pipe_in_prose_is_not_a_table():
    s = "Either A | B works here."  # no leading/trailing pipe → prose, leave it
    assert strip_markdown_tables(s) == s


# ── item 3: the SUGGESTED convention ──────────────────────────────────────────────────
from app.agents.chat_format import extract_suggested_replies  # noqa: E402


def test_suggested_line_is_extracted_and_stripped():
    text = 'Do you have a bill in hand?\n\nSUGGESTED: ["Yes, I have a bill", "No bill yet"]\n'
    stripped, replies = extract_suggested_replies(text)
    assert replies == ["Yes, I have a bill", "No bill yet"]
    assert stripped == "Do you have a bill in hand?"
    assert "SUGGESTED" not in stripped


def test_malformed_suggested_line_is_stripped_but_yields_nothing():
    stripped, replies = extract_suggested_replies('Answer.\nSUGGESTED: ["unterminated')
    assert replies == [] and stripped == "Answer."  # the raw convention never renders
    stripped, replies = extract_suggested_replies("Answer.\nSUGGESTED: not-json")
    assert replies == [] and stripped == "Answer."
    stripped, replies = extract_suggested_replies('Answer.\nSUGGESTED: {"a": 1}')
    assert replies == [] and stripped == "Answer."


def test_suggested_caps_and_hygiene():
    text = 'Q?\nSUGGESTED: ["one", "two", "three", "four", "five", 7, "this one is far too long to be a chip"]'
    _, replies = extract_suggested_replies(text)
    assert replies == ["one", "two", "three", "four"]  # max 4, non-strings and long items skipped
    _, replies = extract_suggested_replies('Q?\nSUGGESTED: ["dup", "dup", "  spaced   out  "]')
    assert replies == ["dup", "spaced out"]


def test_suggested_only_honored_at_the_end():
    text = 'SUGGESTED: ["early"]\nThen a real answer follows.'
    stripped, replies = extract_suggested_replies(text)
    assert replies == [] and stripped == text  # mid-text = confusion, left as ordinary text
    assert extract_suggested_replies("") == ("", [])
    assert extract_suggested_replies("plain answer") == ("plain answer", [])
