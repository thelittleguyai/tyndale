"""Phase CO-10 — chat-mode prompt selection + Lead Planner branching."""

from __future__ import annotations

from app.agents import lead_planner
from app.agents.chat import looks_like_specific_situation, tool_names_for
from app.agents.context_loader import compose_chat_system_prompt


def _text(blocks: list[dict]) -> str:
    return "\n".join(b["text"] for b in blocks)


def test_per_case_mode_prompt_includes_case_context_block():
    text = _text(compose_chat_system_prompt("per_case"))
    assert "PER-CASE MODE" in text
    assert "case file" in text.lower()
    assert "pg_case_file_get" in tool_names_for("per_case")


def test_freeform_mode_prompt_does_not_include_case_context():
    text = _text(compose_chat_system_prompt("freeform"))
    assert "FREEFORM MODE" in text
    # Freeform never gets case-file tools — the mode boundary is enforced in code.
    assert "pg_case_file_get" not in tool_names_for("freeform")


def test_lead_planner_branches_correctly_on_chat_mode():
    assert lead_planner.chat_mode_for_case(None) == "freeform"
    assert lead_planner.chat_mode_for_case("some-case-id") == "per_case"
    pc = _text(lead_planner.chat_system_blocks("per_case"))
    ff = _text(lead_planner.chat_system_blocks("freeform"))
    assert pc != ff
    assert "PER-CASE" in pc and "FREEFORM" in ff


def test_specific_situation_detector():
    assert looks_like_specific_situation("I got a $4,200 bill and Aetna paid $800")
    assert not looks_like_specific_situation("what does CPT 27447 mean")
