"""llm_health — last-Claude-call recorder + routing-path label (admin diagnosability)."""

from __future__ import annotations

from app.agents import llm_health
from app.config import Settings


def _s(**over) -> Settings:
    return Settings(database_url="postgresql+asyncpg://u:p@localhost/db", **over)  # type: ignore[arg-type]


def test_record_and_read_roundtrip():
    llm_health.record_claude_call(ok=False, path="foundry", detail="AuthError")
    last = llm_health.last_claude_call()
    assert last["status"] == "error"
    assert last["path"] == "foundry"
    assert last["detail"] == "AuthError"
    assert last["at"]  # timestamp stamped

    llm_health.record_claude_call(ok=True, path="foundry")
    ok = llm_health.last_claude_call()
    assert ok["status"] == "ok"
    assert ok["detail"] is None


def test_claude_path_label():
    assert (
        llm_health.claude_path_label(
            _s(use_foundry=True, foundry_endpoint="https://x.services.ai.azure.com")
        )
        == "foundry"
    )
    assert llm_health.claude_path_label(_s(anthropic_api_key="sk-ant-x")) == "anthropic-direct"
    assert (
        llm_health.claude_path_label(_s(litellm_proxy_url="http://proxy:4001"))
        == "anthropic-direct"
    )
    assert llm_health.claude_path_label(_s(anthropic_api_key="<placeholder>")) == "stub"
    assert llm_health.claude_path_label(_s()) == "stub"
