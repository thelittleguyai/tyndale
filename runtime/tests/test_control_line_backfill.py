"""Old messages with raw control lines are re-parsed — e2e re-test 2026-09-23, item 5.

Messages persisted before 2ac1e47 carry ``SUGGESTED: [...]`` above the footer and fenced
``CTA: create_case`` lines. The app strips them at render (apps/mobile/lib/control-lines.ts);
migration 0059 fixes the rows. Three parsers, one behaviour — held to ONE case file:

  * the live server parser (chat_format.extract_directives, then scrub_control_lines),
  * the migration's frozen copy (a migration must not import app code that can move),
  * the app's render-time sanitizer (its jest suite reads the same file).
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents.chat_format import extract_directives, scrub_control_lines
from app.db.base import AsyncSessionLocal
from app.db.models.messages import Message

HERE = pathlib.Path(__file__).resolve().parent
CASES = json.loads((HERE / "fixtures/control_line_cases.json").read_text(encoding="utf-8"))["cases"]
FOOTER = "Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice."


def _migration():
    path = HERE.parent / "app/db/migrations/versions/0059_control_line_backfill.py"
    spec = importlib.util.spec_from_file_location("m0059", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("case", CASES, ids=[c["input"][:30] for c in CASES])
def test_the_shared_cases_are_still_what_the_server_parser_does(case):
    clean, replies, cta = extract_directives(case["input"])
    clean, _ = scrub_control_lines(clean)
    assert (clean, replies, cta) == (case["text"], case["replies"], case["cta"]), (
        "the server parser moved — regenerate tests/fixtures/control_line_cases.json and "
        "bring apps/mobile/lib/control-lines.ts along"
    )


@pytest.mark.parametrize("case", CASES, ids=[c["input"][:30] for c in CASES])
def test_the_migrations_frozen_parser_agrees(case):
    text, replies, cta, _changed = _migration().sanitize(case["input"])
    assert (text, replies, cta) == (case["text"], case["replies"], case["cta"])


async def _conversation_with(client: AsyncClient, **fields) -> tuple[str, str]:
    conv_id = (await client.post("/v1/conversations", json={})).json()["conversation_id"]
    mid = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add(Message(message_id=mid, conversation_id=uuid.UUID(conv_id), sequence_number=2, role="assistant",
                      kind="message", status="complete", **fields))
        await s.commit()
    return conv_id, str(mid)


async def _run_backfill() -> int:
    mod = _migration()
    async with AsyncSessionLocal() as s:
        n = await s.run_sync(lambda sync: mod.backfill(sync.connection()))
        await s.commit()
    return n


@pytest.mark.asyncio
async def test_the_migration_fixes_the_rows_themselves_and_is_idempotent(client: AsyncClient):
    conv_id, mid = await _conversation_with(
        client,
        content=f"Let's get your case started.\n\n```\nCTA: create_case\n```\nSUGGESTED: [\"Yes, I have a bill\", \"No bill yet\"]\n\n{FOOTER}",
        content_chunks=[{"tier": "A", "text": "Let's get your case started.\n`CTA: create_case`", "citations": []}],
        citations=[],
        suggested_replies=None,
    )
    assert await _run_backfill() >= 1

    got = (await client.get(f"/v1/conversations/{conv_id}")).json()
    msg = next(m for m in got["messages"] if m["message_id"] == mid)
    assert "SUGGESTED" not in msg["content"] and "CTA" not in msg["content"] and "```" not in msg["content"]
    assert msg["content"].endswith(FOOTER)
    assert all("CTA" not in c["text"] for c in msg["content_chunks"])
    assert msg["suggested_replies"] == ["Yes, I have a bill", "No bill yet"]  # the chips' field
    assert [c for c in msg["citations"] if c.get("action_type") == "create_case_cta"]  # the button's

    # a second run finds nothing left to fix on this row
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(Message).where(Message.message_id == uuid.UUID(mid)))).scalar_one()
        snapshot = (before.content, before.content_chunks, before.citations, before.suggested_replies)
    await _run_backfill()
    async with AsyncSessionLocal() as s:
        after = (await s.execute(select(Message).where(Message.message_id == uuid.UUID(mid)))).scalar_one()
    assert (after.content, after.content_chunks, after.citations, after.suggested_replies) == snapshot


@pytest.mark.asyncio
async def test_a_rows_own_chips_and_button_are_kept_and_clean_rows_are_untouched(client: AsyncClient):
    conv_id, mid = await _conversation_with(
        client,
        content='Answer.\nSUGGESTED: ["From the line"]',
        content_chunks=[],
        citations=[{"action_type": "create_case_cta", "title": "Create a case"}],
        suggested_replies=["Its own chip"],
    )
    clean_conv, clean_mid = await _conversation_with(client, content="Plain answer.", content_chunks=[], citations=[], suggested_replies=None)
    await _run_backfill()
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Message).where(Message.message_id == uuid.UUID(mid)))).scalar_one()
        clean = (await s.execute(select(Message).where(Message.message_id == uuid.UUID(clean_mid)))).scalar_one()
    assert row.content == "Answer." and row.suggested_replies == ["Its own chip"]
    assert len([c for c in row.citations if c.get("action_type") == "create_case_cta"]) == 1  # not doubled
    assert clean.content == "Plain answer." and clean.suggested_replies is None
    del conv_id, clean_conv
