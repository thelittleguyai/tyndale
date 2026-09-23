"""Control lines never render (e2e 2026-09-23 B3).

The specimen conversation persisted `SUGGESTED: [...]` above the disclaimer footer and a
later message with a ```-fenced `CTA: create_case` — no chips, no button, raw syntax on
screen. The tail-only parsers matched a bare final line and nothing else. Now: found
anywhere, fenced or decorated or not, last occurrence wins, the footer stays; a malformed
payload is stripped and yields nothing; and a persisted assistant message NEVER carries the
raw convention — the eval fails on it, the runtime strips and logs it.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.agents.chat_contract import freeform_contract_violations
from app.agents.chat_format import extract_directives, has_raw_control_line, scrub_control_lines

FOOTER = "Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice."


# ── the specimen's two shapes ──────────────────────────────────────────────────────────
def test_suggested_above_the_footer_becomes_chips_and_the_footer_stays():
    text = f'Do you have the bill in hand?\nSUGGESTED: ["Yes, I have a bill", "No bill yet"]\n\n{FOOTER}'
    clean, replies, cta = extract_directives(text)
    assert replies == ["Yes, I have a bill", "No bill yet"] and cta is None
    assert clean == f"Do you have the bill in hand?\n\n{FOOTER}"
    assert not has_raw_control_line(clean)


def test_a_fenced_cta_becomes_the_button_and_the_fence_goes_with_it():
    text = f"Let's get your case started — tap below to upload your bill.\n\n```\nCTA: create_case\n```\n\n{FOOTER}"
    clean, replies, cta = extract_directives(text)
    assert cta == "create_case" and replies == []
    assert "```" not in clean and "CTA" not in clean and clean.endswith(FOOTER)


@pytest.mark.parametrize(
    "line",
    ["```CTA: create_case```", "`CTA: create_case`", "**CTA: create_case**", "CTA: create_case.", "```text\nCTA: create_case\n```"],
)
def test_every_decoration_the_model_adds_is_tolerated(line):
    clean, _, cta = extract_directives(f"Answer.\n{line}\n{FOOTER}")
    assert cta == "create_case" and clean == f"Answer.\n{FOOTER}"


def test_both_in_one_message_in_either_order_and_the_last_occurrence_wins():
    text = f'Answer.\nCTA: create_case\nSUGGESTED: ["A", "B"]\n{FOOTER}\nSUGGESTED: ["C"]'
    clean, replies, cta = extract_directives(text)
    assert replies == ["C"] and cta == "create_case" and clean == f"Answer.\n{FOOTER}"
    text = 'Answer.\n`SUGGESTED: ["A"]`\n\n```\nCTA: create_case\n```'
    clean, replies, cta = extract_directives(text)
    assert replies == ["A"] and cta == "create_case" and clean == "Answer."


def test_malformed_suggested_json_is_stripped_and_ignored_gracefully():
    clean, replies, cta = extract_directives('Answer.\nSUGGESTED: [not json, "x"\nMore.')
    assert replies == [] and cta is None and clean == "Answer.\nMore."
    clean, replies, _ = extract_directives('Answer.\nSUGGESTED: ["Good"]\nSUGGESTED: {oops')
    assert replies == ["Good"] and clean == "Answer."  # a later malformed line does not erase a good one
    clean, _, cta = extract_directives("Answer.\nCTA: delete_everything")
    assert cta is None and clean == "Answer."  # unknown action: stripped, never honoured


def test_the_validator_strips_and_reports_whatever_slipped_through():
    text = "Answer.\n> SUGGESTED: [\"x\"]\nCTA :create_case\nTail."
    assert has_raw_control_line(text)
    clean, found = scrub_control_lines(text)
    assert found == ["SUGGESTED", "CTA"] and clean == "Answer.\nTail."
    assert scrub_control_lines("clean text") == ("clean text", [])
    # the eval contract names it
    assert "raw_control_line" in freeform_contract_violations('Fine answer.\nSUGGESTED: ["a"]')
    assert "raw_control_line" not in freeform_contract_violations("Fine answer.")


def test_the_mode_prompt_shows_the_lines_bare_and_after_the_footer():
    import pathlib

    text = pathlib.Path(__file__).resolve().parents[2].joinpath(
        "intelligence-layer/prompts/chat_modes/freeform_mode.md"
    ).read_text(encoding="utf-8")
    assert "```\nCTA: create_case\n```" not in text and "```\nSUGGESTED:" not in text  # the fenced examples the model copied
    assert "NO code fence" in text and "after the footer" in text


# ── the round trip: stream → persist → the client's fields ─────────────────────────────
@pytest.mark.asyncio
async def test_a_leaked_control_line_is_never_persisted_and_the_chips_still_arrive(client: AsyncClient, monkeypatch):
    """Drive the streaming route with a turn whose text carries a raw control line the
    extractor missed: the persisted message has no `SUGGESTED:`/`CTA:`, the chips and the
    CTA still ride on their own fields (what ChatMessage → SuggestedReplies / CreateCaseCta
    render), and the leak is logged."""
    import json

    from app.routes import messages as messages_route

    async def fake_turn(**_kw):
        yield {"event": "assistant_message_started", "data": {}}
        yield {
            "event": "complete",
            "data": {
                "content": f"Do you have the bill?\n> SUGGESTED: [\"leaked\"]\n{FOOTER}",
                "content_chunks": [{"tier": "A", "text": "Do you have the bill?\nCTA: create_case", "citations": []}],
                "citations": [{"action_type": "create_case_cta", "title": "Create a case"}],
                "confidence_overall": None,
                "suggested_replies": ["Yes, I have a bill", "No bill yet"],
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "tool_calls": [],
            },
        }

    monkeypatch.setattr(messages_route, "stream_chat_turn", fake_turn)
    cid = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
    events: list[dict] = []
    async with client.stream("POST", f"/v1/conversations/{cid}/messages", json={"content": "Think I'm overcharged"}) as resp:
        assert resp.status_code == 200
        cur: dict = {}
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                cur = {"event": line.split(":", 1)[1].strip()}
            elif line.startswith("data:"):
                cur["data"] = json.loads(line.split(":", 1)[1].strip())
                events.append(cur)
                cur = {}
    done = next(e for e in events if e["event"] == "assistant_message_completed")
    mid = done["data"]["message_id"]
    got = await client.get(f"/v1/conversations/{cid}")
    asst = next(m for m in got.json()["messages"] if m["message_id"] == mid)
    assert "SUGGESTED" not in asst["content"] and "CTA" not in asst["content"]
    assert all("CTA" not in c["text"] for c in asst["content_chunks"])
    assert asst["content"].endswith(FOOTER)
    assert asst["suggested_replies"] == ["Yes, I have a bill", "No bill yet"]  # the chips' field
    assert any(c.get("action_type") == "create_case_cta" for c in asst["citations"])  # the button's field
