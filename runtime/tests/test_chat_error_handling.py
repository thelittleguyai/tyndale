"""A raw provider/auth exception must NEVER reach the user.

Covers the real chat path (agents/chat._real_stream → SSE events) and the audit path
(agents/runner.run_agent). Both log + record server-side and surface only the generic
CLAUDE_UNAVAILABLE_MESSAGE; the distinctive raw text below must appear in no SSE payload.
"""

from __future__ import annotations

import json

import pytest

# A raw provider error like the deployed invalid_scope failure, with a distinctive marker.
RAW = "DefaultAzureCredential failed ... ManagedIdentityCredential (invalid_scope) 400 RAWSECRET"


class _FakeStreamCtx:
    async def __aenter__(self):
        raise RuntimeError(RAW)

    async def __aexit__(self, *a):
        return False


class _FakeMessages:
    def stream(self, **kwargs):
        return _FakeStreamCtx()

    async def create(self, **kwargs):
        raise RuntimeError(RAW)


class _FakeClient:
    messages = _FakeMessages()


class _NoCrisis:
    crisis_detected = False


@pytest.mark.asyncio
async def test_real_chat_stream_never_leaks_provider_error(monkeypatch):
    from app.agents import chat, llm_health

    monkeypatch.setattr(chat, "_client", lambda: _FakeClient())
    monkeypatch.setattr(chat, "real_claude_enabled", lambda: True)

    async def _no_crisis(_inp):
        return _NoCrisis()

    monkeypatch.setattr(chat, "crisis_classifier_async", _no_crisis)

    events = [
        ev
        async for ev in chat.stream_chat_turn(
            mode="freeform",
            case_id=None,
            user_id="u1",
            history=[],
            user_message="what does my bill mean",
        )
    ]

    # Exactly one generic error event, and no successful completion.
    errs = [e for e in events if e["event"] == "error"]
    assert len(errs) == 1
    assert errs[0]["data"]["message"] == llm_health.CLAUDE_UNAVAILABLE_MESSAGE
    assert not [e for e in events if e["event"] == "complete"]

    # No fragment of the raw provider exception appears in ANY event payload.
    blob = json.dumps(events, default=str)
    for leak in ("RAWSECRET", "invalid_scope", "DefaultAzureCredential", "ManagedIdentity"):
        assert leak not in blob, f"provider text leaked: {leak}"

    assert llm_health.last_claude_call()["status"] == "error"


@pytest.mark.asyncio
async def test_audit_run_agent_sanitizes_provider_error(monkeypatch):
    from app.agents import llm_health, runner

    monkeypatch.setattr(runner, "_client", lambda: _FakeClient())

    with pytest.raises(llm_health.ProviderUnavailableError) as ei:
        await runner.run_agent(
            model="claude-sonnet-4-6",
            system_blocks=[],
            tool_names=[],
            initial_user_message="run the audit",
            case_file_id="c1",
            actor="bill_detective",
        )

    msg = str(ei.value)
    assert msg == llm_health.CLAUDE_UNAVAILABLE_MESSAGE
    for leak in ("RAWSECRET", "invalid_scope", "DefaultAzureCredential"):
        assert leak not in msg
    assert llm_health.last_claude_call()["status"] == "error"
