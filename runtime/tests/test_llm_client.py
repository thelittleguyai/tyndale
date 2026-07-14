"""CO-18 — the single Claude client factory + Foundry (managed-identity) routing.

Covers model resolution (Anthropic model id <-> Foundry deployment name), the
``_client()`` factory choosing Foundry vs Anthropic-direct, managed identity
counting as real creds in BOTH real-vs-fixture gates, and the production-safety
assertion requiring the Foundry BAA path (DL-79).
"""

from __future__ import annotations

import pytest

from app.config import Settings


def _settings(**over) -> Settings:
    base = {"database_url": "postgresql+asyncpg://u:p@localhost/db"}
    base.update(over)
    return Settings(**base)  # type: ignore[arg-type]


# --- model resolution -------------------------------------------------------


def test_resolved_model_identity_when_foundry_off():
    s = _settings(use_foundry=False)
    assert s.resolved_model("claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_resolved_model_defaults_to_model_id_under_foundry():
    # Deployments are named = the model ids (see infra/envs/dev/ai_foundry.tf), so
    # with no override the deployment name the runtime passes equals the model id.
    s = _settings(use_foundry=True, foundry_endpoint="https://x.services.ai.azure.com")
    assert s.resolved_model("claude-sonnet-4-6") == "claude-sonnet-4-6"
    assert s.resolved_model("claude-haiku-4-5") == "claude-haiku-4-5"


def test_resolved_model_uses_deployment_overrides():
    s = _settings(
        use_foundry=True,
        foundry_endpoint="https://x.services.ai.azure.com",
        foundry_deployment_sonnet="sonnet-dep",
        foundry_deployment_haiku="haiku-dep",
    )
    assert s.resolved_model("claude-sonnet-4-6") == "sonnet-dep"
    assert s.resolved_model("claude-haiku-4-5") == "haiku-dep"


def test_claude_model_for_resolves_under_foundry():
    s = _settings(
        use_foundry=True,
        foundry_endpoint="https://x.services.ai.azure.com",
        foundry_deployment_sonnet="sonnet-dep",
    )
    assert s.claude_model_for("bill_detective") == "sonnet-dep"


# --- creds gates recognize managed identity --------------------------------


def test_creds_gates_accept_managed_identity():
    from app.agents.orchestrator import _has_real_anthropic_creds as orch_creds
    from app.agents.runner import has_real_anthropic_creds as runner_creds

    s = _settings(
        use_foundry=True,
        foundry_endpoint="https://x.services.ai.azure.com",
        anthropic_api_key=None,  # no key — managed identity is the credential
    )
    assert runner_creds(s) is True
    assert orch_creds(s) is True


def test_creds_gates_reject_placeholder_without_foundry():
    from app.agents.runner import has_real_anthropic_creds as runner_creds

    s = _settings(use_foundry=False, anthropic_api_key="<from terraform output>")
    assert runner_creds(s) is False


# --- _client() factory ------------------------------------------------------


def test_client_builds_foundry_client(monkeypatch):
    import app.agents.runner as runner
    from anthropic import AsyncAnthropicFoundry

    s = _settings(
        use_foundry=True,
        foundry_endpoint="https://acct.services.ai.azure.com",
        foundry_token_scope="https://ai.azure.com/.default",
    )
    monkeypatch.setattr(runner, "get_settings", lambda: s)
    client = runner._client()
    assert isinstance(client, AsyncAnthropicFoundry)
    # base_url is the account endpoint + /anthropic (the Messages API path).
    assert str(client.base_url).rstrip("/").endswith("/anthropic")


def test_client_builds_anthropic_direct_when_foundry_off(monkeypatch):
    import app.agents.runner as runner
    from anthropic import AsyncAnthropic

    s = _settings(use_foundry=False, anthropic_api_key="sk-ant-test")
    monkeypatch.setattr(runner, "get_settings", lambda: s)
    client = runner._client()
    assert isinstance(client, AsyncAnthropic)
    assert not isinstance(client, __import__("anthropic").AsyncAnthropicFoundry)


def test_foundry_ignored_when_endpoint_missing(monkeypatch):
    # use_foundry true but no endpoint yet (pre-provision) must NOT build a Foundry
    # client with an empty URL — falls back to Anthropic-direct.
    import app.agents.runner as runner
    from anthropic import AsyncAnthropic, AsyncAnthropicFoundry

    s = _settings(use_foundry=True, foundry_endpoint=None, anthropic_api_key="sk-ant-x")
    monkeypatch.setattr(runner, "get_settings", lambda: s)
    client = runner._client()
    assert isinstance(client, AsyncAnthropic)
    assert not isinstance(client, AsyncAnthropicFoundry)


# --- production-safety assertion (DL-79) -----------------------------------


def test_production_requires_foundry():
    s = _settings(
        node_env="production",
        use_real_claude=True,
        allow_fixture_fallback=False,
        use_foundry=False,  # the violation
        foundry_endpoint=None,
    )
    with pytest.raises(RuntimeError, match="USE_FOUNDRY"):
        s.assert_production_safety()


def test_production_safe_with_foundry(real_orchestration_script):
    s = _settings(
        node_env="production",
        use_real_claude=True,
        allow_fixture_fallback=False,
        use_foundry=True,
        foundry_endpoint="https://x.services.ai.azure.com",
        use_real_auth=True,
        use_real_ocr=True,
    )
    s.assert_production_safety()  # no raise


def test_development_ignores_foundry_requirement():
    # NODE_ENV=development (the dev env) must boot even with Foundry off.
    s = _settings(node_env="development", use_foundry=False)
    s.assert_production_safety()  # no raise
