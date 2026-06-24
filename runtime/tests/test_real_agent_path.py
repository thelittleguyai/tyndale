"""CO-16 part 1 — the real-agent orchestration path under test (no live API).

The fixture short-circuit means the existing suite never exercises the real
Bill Detective → Math Person → Lead Planner sequence. Here a scripted fake
Anthropic client drives that real path through ``runner.run_agent`` (with the
CO-15 hook spine live), the REAL ``pg_upsert_finding`` tool persists a
three-number finding, and we assert ``_assemble_result`` projects the
three-number audit shape. No network / API key needed — the client is replaced
with deterministic, replayable responses (a hand-authored cassette; a true VCR
recording would need a real key and is a follow-on).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import runner
from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent


# --- a scripted fake Anthropic client ---------------------------------------
class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    input_tokens = 12
    output_tokens = 8


class _Resp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = _Usage()


class _FakeMessages:
    """First create() → a pg_upsert_finding tool_use carrying the three numbers
    (so the first agent persists the finding); every later call → end_turn (so the
    remaining agents run through run_agent and terminate cleanly)."""

    def __init__(self, finding_args):
        self.calls = 0
        self.finding_args = finding_args

    async def create(self, **kw):
        self.calls += 1
        if self.calls == 1:
            return _Resp(
                [
                    _Blk(
                        type="tool_use", id="tu1", name="pg_upsert_finding", input=self.finding_args
                    )
                ],
                "tool_use",
            )
        return _Resp([_Blk(type="text", text="Done — the finding is recorded.")], "end_turn")


class _FakeClient:
    def __init__(self, finding_args):
        self.messages = _FakeMessages(finding_args)


@pytest.mark.asyncio
async def test_real_agent_path_persists_and_assembles_three_numbers(
    client: AsyncClient, monkeypatch
):
    from app.agents.orchestrator import run_audit
    from app.config import get_settings

    # A real case so the finding's case_file_id resolves.
    up = await client.post(
        "/v1/upload", files={"file": ("bill.txt", b"sample mri bill", "text/plain")}
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]

    # Force the REAL agent branch (creds gate passes on a fake sk- key) but route
    # the LLM to the scripted fake — no network call is made.
    s = get_settings()
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "litellm_proxy_url", None)

    finding_args = {
        "case_file_id": case_id,
        "finding_type": "payer_side",
        "category": "cost_sharing_miscalculation",
        "voice_tier": "B",
        "subagent_source": "math_person",
        "facts": {
            "provider_billed": 1200.0,
            "eob_member_responsibility": 1200.0,
            "tyndale_computed": 560.0,
            "gap": 640.0,
        },
    }
    monkeypatch.setattr(runner, "_client", lambda: _FakeClient(finding_args))

    result = await run_audit(case_id)

    # The three agents executed through run_agent; the REAL pg_upsert_finding wrote
    # the finding; _assemble_result projected the three-number audit.
    assert result.status == "complete"
    assert result.audit is not None
    assert result.audit.provider_billed == 1200.0
    assert result.audit.eob_member_responsibility == 1200.0
    assert result.audit.tyndale_computed == 560.0
    assert len(result.findings) >= 1
    payer = [f for f in result.findings if f.finding_type == "payer_side"]
    assert payer, "expected the persisted payer_side three-number finding"

    # PostToolUse fired in the real path — a tool_invocation audit row exists for
    # the executed pg_upsert_finding (proves the hook spine ran, not a fixture).
    async with AsyncSessionLocal() as sess:
        rows = (
            (
                await sess.execute(
                    select(AuditEvent).where(AuditEvent.case_file_id == uuid.UUID(case_id))
                )
            )
            .scalars()
            .all()
        )
    assert any(
        r.event_type == "tool_invocation" and r.tools_invoked == ["pg_upsert_finding"] for r in rows
    ), "expected a PostToolUse tool_invocation audit row from the real path"
