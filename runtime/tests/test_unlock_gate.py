"""The first-case unlock moment while billing is dark (doc 40 open question 2 — PROVISIONAL,
Phil decides): `unlock_gate_mode` = free_beta | block | billing, behind the existing
ENABLE_FIRST_CASE_UNLOCK flag (default off — the moment stays dark in every env until flipped)."""

from __future__ import annotations

import uuid

import pytest

# ── the unlock moment while billing is dark (PROVISIONAL — doc 40 open question 2) ────────
@pytest.mark.parametrize(
    ("mode", "proceeds", "must_say", "must_not_say"),
    [("free_beta", True, "Free while we're in beta.", "$4.99"),
     ("block", False, "This step is not open yet.", "$4.99"),
     ("billing", False, "One payment.", "beta")],
)
@pytest.mark.asyncio
async def test_the_unlock_moment_never_states_a_price_nobody_is_charged(monkeypatch, mode, proceeds, must_say, must_not_say):
    from types import SimpleNamespace

    from app.agents import thread_bridge as tb

    emitted: list[dict] = []

    async def ensure(key, kind, payload, *_):
        emitted.append({"key": key, "kind": kind, **payload})

    audit = SimpleNamespace(eob_member_responsibility=900.0, tyndale_computed=511.0)

    async def fake_assemble(_id, composed=""):
        return SimpleNamespace(audit=audit)

    monkeypatch.setattr("app.agents.orchestrator._assemble_result", fake_assemble)
    case = SimpleNamespace(case_file_id=uuid.uuid4())
    for flag_on in (False, True):
        monkeypatch.setattr(tb, "get_settings", lambda on=flag_on: SimpleNamespace(enable_first_case_unlock=on, unlock_gate_mode=mode))
        await tb._ensure_unlock_moment(None, None, case, ensure)
        if not flag_on:
            assert emitted == []  # dark unless ENABLE_FIRST_CASE_UNLOCK — unchanged for every env today
    (moment,) = emitted
    assert moment["variant"] == "first_case_unlock" and moment["gate_mode"] == mode
    assert moment["proceeds"] is proceeds and bool(moment["next_route"]) is proceeds
    text = " ".join([moment["headline"], moment["footnote"], *moment["value_points"]])
    assert "$389.00" in text and must_say in text and must_not_say not in text
    assert len(moment["value_points"]) == 3 and not any("✓" in p for p in moment["value_points"])

    audit.tyndale_computed = 900.0  # no gap → nothing to unlock → no moment
    emitted.clear()
    await tb._ensure_unlock_moment(None, None, case, ensure)
    assert emitted == []
