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
