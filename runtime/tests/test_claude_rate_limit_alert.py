"""A Claude 429 is its own "Needs a person" item, with the quota in the way (e2e re-test
2026-09-23, item 7). The re-test found the Foundry deployment throttling a whole afternoon of
audits while Admin › System said only "Last Claude call: error"."""

from __future__ import annotations

import pathlib

import pytest
from httpx import AsyncClient

from app.agents import llm_health
from app.config import get_settings

REPO = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_ledger():
    llm_health._rate_limits.clear()
    yield
    llm_health._rate_limits.clear()


@pytest.mark.asyncio
async def test_a_throttled_deployment_is_named_with_its_capacity(client: AsyncClient, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "foundry_deployment_sonnet", "claude-sonnet-4-6")
    monkeypatch.setattr(s, "foundry_sonnet_capacity", 25)
    for _ in range(3):
        llm_health.record_rate_limit(
            path="foundry", retry_after=31.0,
            headers={"x-ratelimit-remaining-tokens": "0", "x-ratelimit-limit-tokens": "25000", "authorization": "Bearer secret"},
        )
    body = (await client.get("/v1/admin/system/health")).json()
    assert body["claude_rate_limits"]["count"] == 3
    alert = next(a for a in body["alerts"] if a["kind"] == "claude_rate_limited")
    assert alert["severity"] == "high"
    assert "claude-sonnet-4-6" in alert["detail"] and "25K tokens/min" in alert["detail"]
    assert "x-ratelimit-limit-tokens=25000" in alert["detail"] and "Retry-After 31.0s" in alert["detail"]
    assert "foundry_sonnet_capacity" in alert["action"]
    # numbers only — never a header that could carry a secret
    assert "secret" not in str(body["claude_rate_limits"]) and "Bearer" not in alert["detail"]


@pytest.mark.asyncio
async def test_no_throttling_no_item(client: AsyncClient):
    body = (await client.get("/v1/admin/system/health")).json()
    assert body["claude_rate_limits"]["count"] == 0
    assert "claude_rate_limited" not in {a["kind"] for a in body["alerts"]}


def test_one_throttled_call_is_medium_and_the_capacity_reaches_the_runtime():
    from app.routes.admin.system import _claude_rate_limit_alert

    llm_health.record_rate_limit(path="foundry", retry_after=None, headers={})
    alert = _claude_rate_limit_alert(llm_health.rate_limit_snapshot())
    assert alert and alert["severity"] == "medium"
    compute = (REPO / "infra/envs/dev/compute.tf").read_text()
    assert 'name  = "FOUNDRY_SONNET_CAPACITY"' in compute and "var.foundry_sonnet_capacity" in compute
