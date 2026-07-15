"""Admin analytics endpoint (Internal Analytics P0). The client fixture is the dev admin, so it
reaches the admin-gated route. Rule 1 is verified at the API boundary: every ratio ships its raw
numerator, denominator, AND a non-empty definition, so the dashboard can never render a percentage
without the n/d and the definition beside it."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_analytics_serves_panels_and_every_ratio_names_its_denominator(client: AsyncClient):
    r = await client.get("/v1/admin/analytics?days=90")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 90
    panel_keys = {p["key"] for p in body["panels"]}
    assert {"funnel", "engagement", "outcomes", "accuracy", "compliance"} <= panel_keys

    for panel in body["panels"]:
        for m in panel["metrics"]:
            assert m["definition"].strip(), f"{m['key']} has no definition (Rule 1)"
            if m["kind"] == "ratio":
                # A ratio must carry n and d so the UI shows them beside the %.
                assert m["numerator"] is not None
                assert m["denominator"] is not None

    # win rate and its report-rate denominator are both present (the UI hard-pairs them).
    outcomes = next(p for p in body["panels"] if p["key"] == "outcomes")
    keys = {m["key"] for m in outcomes["metrics"]}
    assert {"win_rate", "outcome_report_rate"} <= keys

    status = body["status"]
    assert "enable_record_view" in status["flags"]
    assert "analytics_rollup" in status["crons"]
    assert "unlock_purchased" in status["not_yet_live_events"]  # billing events registered, not live


@pytest.mark.asyncio
async def test_admin_analytics_requires_admin(client: AsyncClient, monkeypatch):
    # A non-admin identity gets 404 (anti-enumeration), never 200.
    from app.auth import CurrentUser, current_user
    from app.main import app

    async def _non_admin() -> CurrentUser:
        return CurrentUser(
            user_id=__import__("uuid").UUID("00000000-0000-0000-0000-0000000000e1"),
            email="not-admin@example.com", first_name="Nope", user_type="member",
        )

    app.dependency_overrides[current_user] = _non_admin
    try:
        r = await client.get("/v1/admin/analytics")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(current_user, None)
