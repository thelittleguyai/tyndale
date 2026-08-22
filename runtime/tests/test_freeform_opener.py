"""Item 4 (Brock 2026-08-22): the freeform opener + chips live in the orchestration-script
registry (Brock-owned, drift-guarded once authored) and reach the client via the copy
surface. Shippable seed copy — never a [PLACEHOLDER-eng] (that would block staging)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.agents.context_loader import PLACEHOLDER_PREFIX, load_orchestration_registry


def test_opener_keys_exist_unmapped_and_shippable():
    reg = load_orchestration_registry()
    for key in ("freeform_opener", "freeform_opener_chips"):
        entry = reg[key]
        assert entry.source.startswith("UNMAPPED"), key  # exempt from the verbatim guard by class
        assert not entry.text.startswith(PLACEHOLDER_PREFIX), key
        assert entry.tier == "A"
    chips = [c.strip() for c in reg["freeform_opener_chips"].text.split("·")]
    assert len(chips) == 4 and all(chips)
    assert reg["freeform_opener"].text == "What can I help you with today?"


@pytest.mark.asyncio
async def test_chat_copy_surface_serves_opener_and_chips(client: AsyncClient):
    r = await client.get("/v1/copy/chat")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["opener"] == "What can I help you with today?"
    assert body["opener_chips"].count("·") == 3  # four chips, three separators
