"""CO-15 part 2 — chat-ingress safety + fixture-fallback hardening.

* Crisis: a positive classifier signal returns the DL-04 clean decline and the
  Lead Planner / fixture stream is NOT invoked.
* UserPromptSubmit: block=True short-circuits with a polite notice.
* Production-config: an unsafe prod profile (fixture fallback on, or real-Claude
  off) fails the startup assertion.
* Orchestrator: no three-number finding → degraded status, never {0,0,0}/complete.
* run_audit raises (not the $560 fixture) when creds are missing + fallback off.
"""

from __future__ import annotations

import uuid

import pytest


# --- crisis decline bypasses the Lead Planner -------------------------------
@pytest.mark.asyncio
async def test_crisis_input_declines_and_bypasses_planner(monkeypatch):
    from app.agents import chat
    from app.hooks.contracts import CrisisClassifierResult

    async def _crisis(inp):
        return CrisisClassifierResult(crisis_detected=True)

    monkeypatch.setattr(chat, "crisis_classifier_async", _crisis)

    async def _boom(*a, **k):
        raise AssertionError("crisis decline must NOT reach the Lead Planner / stream")
        yield  # noqa — makes this an async generator

    monkeypatch.setattr(chat, "_fixture_stream", _boom)
    monkeypatch.setattr(chat, "_real_stream", _boom)

    events = [
        ev
        async for ev in chat.stream_chat_turn(
            mode="freeform",
            case_id=None,
            user_id="u1",
            history=[],
            user_message="I don't want to be here anymore.",
        )
    ]
    complete = [e for e in events if e["event"] == "complete"]
    assert complete, "expected a terminal complete event"
    content = complete[0]["data"]["content"]
    assert content == chat._CRISIS_DECLINE
    # DL-04: no 988, no routing of any kind.
    assert "988" not in content


# --- UserPromptSubmit block short-circuits -----------------------------------
@pytest.mark.asyncio
async def test_user_prompt_submit_block_short_circuits(monkeypatch):
    from app.agents import chat
    from app.hooks.contracts import UserPromptSubmitResult

    monkeypatch.setattr(
        chat,
        "user_prompt_submit_hook",
        lambda inp: UserPromptSubmitResult(scrubbed_message=inp.raw_message, block=True),
    )

    async def _boom(*a, **k):
        raise AssertionError("a blocked message must not reach the planner")
        yield  # noqa — async generator

    monkeypatch.setattr(chat, "_fixture_stream", _boom)
    monkeypatch.setattr(chat, "_real_stream", _boom)

    events = [
        ev
        async for ev in chat.stream_chat_turn(
            mode="freeform", case_id=None, user_id="u1", history=[], user_message="hi"
        )
    ]
    complete = [e for e in events if e["event"] == "complete"]
    assert complete and complete[0]["data"]["content"] == chat._BLOCKED_NOTICE


# --- production-config fail-fast assertion -----------------------------------
def test_production_config_assertion(real_orchestration_script):
    from app.config import Settings

    base = dict(database_url="postgresql+asyncpg://u:p@h/d", node_env="production")

    # Unsafe: fixture fallback left on in production.
    with pytest.raises(RuntimeError, match="ALLOW_FIXTURE_FALLBACK"):
        Settings(
            **base, use_real_claude=True, allow_fixture_fallback=True
        ).assert_production_safety()

    # Unsafe: real Claude disabled in production.
    with pytest.raises(RuntimeError, match="USE_REAL_CLAUDE"):
        Settings(
            **base, use_real_claude=False, allow_fixture_fallback=False
        ).assert_production_safety()

    # Unsafe: Foundry off in production (CO-18 / DL-79) — Claude would route
    # Anthropic-direct, outside the Azure BAA.
    with pytest.raises(RuntimeError, match="USE_FOUNDRY"):
        Settings(
            **base, use_real_claude=True, allow_fixture_fallback=False, use_foundry=False
        ).assert_production_safety()

    # Unsafe: dev auth stub left on in production (Phase 1.4).
    with pytest.raises(RuntimeError, match="USE_REAL_AUTH"):
        Settings(
            **base,
            use_real_claude=True,
            allow_fixture_fallback=False,
            use_foundry=True,
            foundry_endpoint="https://x.services.ai.azure.com",
            use_real_auth=False,
            use_real_ocr=True,
        ).assert_production_safety()

    # Unsafe: OCR stub left on in production (Phase 1.4).
    with pytest.raises(RuntimeError, match="USE_REAL_OCR"):
        Settings(
            **base,
            use_real_claude=True,
            allow_fixture_fallback=False,
            use_foundry=True,
            foundry_endpoint="https://x.services.ai.azure.com",
            use_real_auth=True,
            use_real_ocr=False,
        ).assert_production_safety()

    # Safe production profile: real Claude on, no fixture fallback, Foundry on, real auth + OCR.
    Settings(
        **base,
        use_real_claude=True,
        allow_fixture_fallback=False,
        use_foundry=True,
        foundry_endpoint="https://tyndale-prod-foundry.services.ai.azure.com",
        use_real_auth=True,
        use_real_ocr=True,
    ).assert_production_safety()

    # Non-production: never raises, even with an unsafe-looking combo.
    Settings(
        database_url="postgresql+asyncpg://u:p@h/d",
        node_env="development",
        use_real_claude=False,
        allow_fixture_fallback=True,
    ).assert_production_safety()


# --- orchestrator: no zeroed-"complete" audit --------------------------------
@pytest.mark.asyncio
async def test_assemble_result_degrades_without_three_number_finding():
    from app.agents.orchestrator import _assemble_result

    # A case with no findings → no three-number audit. Must NOT come back as
    # {0,0,0}/complete (that reads as "you owe $0").
    result = await _assemble_result(str(uuid.uuid4()), "no audit produced")
    assert result.status == "audit_incomplete"
    assert result.audit is None


@pytest.mark.asyncio
async def test_run_audit_raises_when_creds_missing_and_fallback_off(monkeypatch):
    from app.agents.orchestrator import run_audit
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", None)
    monkeypatch.setattr(s, "litellm_proxy_url", None)
    monkeypatch.setattr(s, "allow_fixture_fallback", False)

    # Raises loudly instead of returning the MRI fixture ($560) as a real audit.
    with pytest.raises(RuntimeError, match="ALLOW_FIXTURE_FALLBACK"):
        await run_audit(str(uuid.uuid4()))
