"""Dashboard welcome-summary guardrails (browser review 2026-07-15). The generator fabricated a
human review loop ("our review team will resume processing"). Guardrails: a banned-pattern
validator, a deterministic count-based fallback, and a per-state cache. THERE ARE NO HUMANS IN
THIS LOOP."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import greeting as greeting_mod
from app.agents.greeting import _deterministic_summary, compose_status_greeting, passes_guardrails
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.users import User
from app.routes import dashboard as dashboard_mod


# --- validator --------------------------------------------------------------
def test_passes_guardrails_rejects_each_banned_pattern():
    banned = [
        "Expect the next update from our review team.",
        "A reviewer will pick up where things left off.",
        "Our team will resume processing them soon.",
        "Our staff is looking into it.",
        "An agent will call you back.",
        "A specialist has been assigned.",
        "You're in the processing queue.",
        "A person will review this.",
    ]
    for b in banned:
        assert passes_guardrails(b) is False, b
    assert passes_guardrails("") is False


def test_passes_guardrails_accepts_clean_factual_summary():
    assert passes_guardrails("You have 2 open cases — 1 needs documents, 1 has results ready.")
    assert passes_guardrails("Re-upload clearer copies to finish reading your bill.")


# --- deterministic fallback -------------------------------------------------
def test_deterministic_summary_counts_by_state():
    out = _deterministic_summary(
        [
            {"status": "audit_incomplete"},
            {"status": "audit_incomplete"},
            {"status": "audit_complete"},
        ]
    )
    assert out and "3 open cases" in out
    assert "2 need documents" in out and "1 with results ready" in out
    assert passes_guardrails(out)  # the fallback itself is always clean


def test_deterministic_summary_none_when_nothing_to_summarize():
    assert _deterministic_summary([]) is None
    assert _deterministic_summary([{"status": "not_a_bill"}, {"status": "archived"}]) is None


# --- generator fallback on rejected / clean output --------------------------
class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Msgs:
    def __init__(self, text):
        self._t = text

    async def create(self, **_kw):
        return _Resp(self._t)


class _FakeClient:
    def __init__(self, text):
        self.messages = _Msgs(text)


@pytest.mark.asyncio
async def test_compose_falls_back_when_model_output_is_rejected(monkeypatch):
    states = [{"status": "audit_incomplete"}, {"status": "audit_complete"}]
    monkeypatch.setattr(get_settings(), "use_real_claude", True)
    monkeypatch.setattr(greeting_mod, "_has_real_anthropic_creds", lambda _s: True)
    monkeypatch.setattr(greeting_mod, "_client", lambda: _FakeClient("Our review team will resume processing them."))
    out = await compose_status_greeting(states)
    assert out == _deterministic_summary(states)  # banned output dropped → deterministic fallback
    assert passes_guardrails(out)


@pytest.mark.asyncio
async def test_compose_uses_a_clean_model_output(monkeypatch):
    states = [{"status": "audit_complete"}]
    monkeypatch.setattr(get_settings(), "use_real_claude", True)
    monkeypatch.setattr(greeting_mod, "_has_real_anthropic_creds", lambda _s: True)
    monkeypatch.setattr(greeting_mod, "_client", lambda: _FakeClient("Your bill has results ready to review."))
    assert await compose_status_greeting(states) == "Your bill has results ready to review."


# --- cache: same state → same words, no regeneration ------------------------
@pytest.mark.asyncio
async def test_welcome_summary_cache_hit_and_regenerates_on_change(client: AsyncClient, monkeypatch):
    async with AsyncSessionLocal() as s:
        uid = (await s.execute(select(User.user_id).limit(1))).scalar_one()
    calls = {"n": 0}

    async def _fake_compose(states):
        calls["n"] += 1
        return f"summary#{calls['n']}"

    monkeypatch.setattr(dashboard_mod, "compose_status_greeting", _fake_compose)

    s1 = [{"status": "audit_incomplete", "next_deadline_date": None, "next_deadline_label": None}]
    async with AsyncSessionLocal() as s:
        first = await dashboard_mod._cached_welcome_summary(s, uid, s1)
    async with AsyncSessionLocal() as s:
        second = await dashboard_mod._cached_welcome_summary(s, uid, s1)
    assert first == second and calls["n"] == 1  # unchanged state → cache hit, no regeneration

    s2 = [{"status": "audit_complete", "next_deadline_date": None, "next_deadline_label": None}]
    async with AsyncSessionLocal() as s:
        third = await dashboard_mod._cached_welcome_summary(s, uid, s2)
    assert third != first and calls["n"] == 2  # changed state → regenerated
