"""Homescreen honest subset (Brock mockups 2026-08-22): the banner states only real computed
case state; unbuilt-feature claims (B8 proactive monitoring) are BANNED from this surface.

Counting logic is unit-tested on the pure composer (the local dev DB shares one fixture
user across every historical test case, so route-level count assertions can't be stable)."""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.routes.dashboard import _compose_banner, _needs_you

# The mockup's B8 claims — banned until that machinery exists (no such flag today).
_BANNED_PHRASES = ("deadlines watched", "numbers re-checked", "re-checked")


def _case(status, reason=None):
    return SimpleNamespace(status=status, audit_incomplete_reason=reason)


def _assert_honest(text: str):
    for phrase in _BANNED_PHRASES:
        assert phrase not in text.lower()


def test_zero_cases_is_the_honest_empty_state():
    b = _compose_banner("Amy", [])
    assert b["title"] == "Welcome back, Amy."
    assert "check a bill" in b["subline"].lower()
    _assert_honest(b["title"] + " " + b["subline"])


def test_counts_derive_from_real_state():
    cases = [
        _case("audit_running"),
        _case("encounter_verification_pending"),
        _case("resolved"),  # terminal — not an open case
    ]
    b = _compose_banner("Amy", cases)
    assert b["subline"] == "2 open cases — 1 needs something from you."
    _assert_honest(b["subline"])


def test_quiet_state_when_nothing_is_blocked_on_the_user():
    b = _compose_banner("Amy", [_case("audit_running"), _case("audit_complete")])
    assert b["subline"] == "2 open cases — nothing needs you right now."
    _assert_honest(b["subline"])


def test_singular_phrasing():
    b = _compose_banner("Amy", [_case("awaiting_eob_confirmation")])
    assert b["subline"] == "1 open case — 1 needs something from you."


def test_needs_you_maps_only_user_actionable_states():
    assert _needs_you(_case("encounter_verification_pending"))
    assert _needs_you(_case("awaiting_eob_confirmation"))
    assert _needs_you(_case("audit_incomplete", reason="needs_documents"))
    assert not _needs_you(_case("audit_incomplete", reason="system_error"))
    assert not _needs_you(_case("audit_running"))
    assert not _needs_you(_case("audit_complete"))


@pytest.mark.asyncio
async def test_dashboard_serves_a_registry_banner(client: AsyncClient):
    r = await client.get("/v1/dashboard")
    assert r.status_code == 200, r.text
    b = r.json()["banner"]
    assert b and b["title"].startswith("Welcome back") and b["subline"]
    assert "MISSING-script" not in b["title"] + b["subline"]
    _assert_honest(b["title"] + " " + b["subline"])


@pytest.mark.asyncio
async def test_stat_fields_present_and_confirmed_only(client: AsyncClient):
    r = await client.get("/v1/dashboard")
    d = r.json()
    assert "recovered_to_date" in d and "open_count" in d and "needs_you_count" in d
    assert d["needs_you_count"] <= d["open_count"]
    assert d["recovered_to_date"] >= 0.0
