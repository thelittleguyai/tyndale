"""CO-15 part 1 — the hook spine wired into the agent loop (runner.run_agent).

Mocks the Anthropic client (scripted tool_use → end_turn) + the tool registry so
no API key / network is needed. Verifies:
  * PreToolUse blocks a PHI send_email: the tool is NOT executed, the model gets
    the block reason, and a phi_block audit_events row is written.
  * PostToolUse writes one tool_invocation audit row per executed tool.
  * The Stop ship-gate ships when citations resolve, and regenerates (≤3) then
    escalates to human_review when a citation never resolves.

The fixture/approve common path is exercised by the existing e2e suite (unchanged).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents import runner
from app.agents.runner import run_agent
from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent


# --- a scriptable fake Anthropic client -------------------------------------
class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    input_tokens = 10
    output_tokens = 5


class _Resp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = _Usage()


def _text(t):
    return _Blk(type="text", text=t)


def _tool(tool_id, name, inp):
    return _Blk(type="tool_use", id=tool_id, name=name, input=inp)


class _FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = 0

    async def create(self, **kw):
        resp = self._scripted[min(self.calls, len(self._scripted) - 1)]
        self.calls += 1
        return resp


class _FakeClient:
    def __init__(self, scripted):
        self.messages = _FakeMessages(scripted)


def _install(monkeypatch, scripted, tool_results=None):
    """Wire a scripted fake client + a recording call_tool into runner; returns
    (fake_client, recorded_tool_names)."""
    fake = _FakeClient(scripted)
    monkeypatch.setattr(runner, "_client", lambda: fake)
    monkeypatch.setattr("app.tools.get_anthropic_tools", lambda names: [])

    calls: list[str] = []
    results = tool_results or {}

    async def fake_call_tool(name, args):
        calls.append(name)
        return results.get(name, {"ok": True})

    monkeypatch.setattr(runner, "call_tool", fake_call_tool)
    return fake, calls


# --- PreToolUse: PHI send_email is blocked + audited, never executed ---------
@pytest.mark.asyncio
async def test_pre_tool_use_blocks_phi_send_email(monkeypatch):
    case_id = str(uuid.uuid4())
    scripted = [
        _Resp(
            [
                _tool(
                    "tu_1",
                    "send_email",
                    {"subject": "Your bill", "body": "Your bill of $1,200 is ready."},
                )
            ],
            "tool_use",
        ),
        _Resp([_text("Understood — I won't send that.")], "end_turn"),
    ]
    _fake, calls = _install(monkeypatch, scripted)

    async with AsyncSessionLocal() as s:
        result = await run_agent(
            model="m",
            system_blocks=[],
            tool_names=["send_email"],
            initial_user_message="go",
            case_file_id=case_id,
            actor="lead_planner",
            session=s,
        )
        await s.commit()

    # send_email was NOT executed.
    assert "send_email" not in calls
    # The model saw the block reason as a tool_result.
    blocked = [tc for tc in result.tool_calls if tc["name"] == "send_email"]
    assert blocked and blocked[0]["result"]["error"] == "blocked_by_policy"
    assert "DL-47" in (blocked[0]["result"]["reason"] or "")
    # Exactly one phi_block audit row written for the case.
    async with AsyncSessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(AuditEvent).where(AuditEvent.case_file_id == uuid.UUID(case_id))
                )
            )
            .scalars()
            .all()
        )
    phi = [r for r in rows if r.event_type == "phi_block"]
    assert len(phi) == 1 and phi[0].outcome == "blocked"


# --- PostToolUse: a successful tool writes one tool_invocation row -----------
@pytest.mark.asyncio
async def test_post_tool_use_writes_audit_row(monkeypatch):
    case_id = str(uuid.uuid4())
    scripted = [
        _Resp([_tool("tu_1", "pg_case_file_get", {"case_file_id": case_id})], "tool_use"),
        _Resp([_text("Loaded the case.")], "end_turn"),
    ]
    _install(
        monkeypatch,
        scripted,
        tool_results={"pg_case_file_get": {"case_file_id": case_id, "status": "ok"}},
    )

    async with AsyncSessionLocal() as s:
        await run_agent(
            model="m",
            system_blocks=[],
            tool_names=["pg_case_file_get"],
            initial_user_message="go",
            case_file_id=case_id,
            actor="bill_detective",
            session=s,
        )
        await s.commit()

    async with AsyncSessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(AuditEvent).where(AuditEvent.case_file_id == uuid.UUID(case_id))
                )
            )
            .scalars()
            .all()
        )
    inv = [r for r in rows if r.event_type == "tool_invocation"]
    assert len(inv) == 1
    assert inv[0].actor == "bill_detective"
    assert inv[0].outcome == "success"
    assert inv[0].tools_invoked == ["pg_case_file_get"]


# --- Stop: resolved citations ship ------------------------------------------
@pytest.mark.asyncio
async def test_stop_ships_when_citations_resolve(monkeypatch):
    case_id = str(uuid.uuid4())
    scripted = [
        _Resp([_tool("tu_1", "qdrant_search_billing_codes", {"query": "mri"})], "tool_use"),
        _Resp([_text("Per the rule [CPT §1, src_abc123] this is unbundled.")], "end_turn"),
    ]
    _install(
        monkeypatch,
        scripted,
        tool_results={
            "qdrant_search_billing_codes": {
                "hits": [{"id": "src_abc123", "score": 0.9, "payload": {"src_id": "src_abc123"}}],
                "count": 1,
            }
        },
    )

    async with AsyncSessionLocal() as s:
        result = await run_agent(
            model="m",
            system_blocks=[],
            tool_names=["qdrant_search_billing_codes"],
            initial_user_message="go",
            case_file_id=case_id,
            actor="math_person",
            session=s,
        )
        await s.commit()

    assert result.stop_action == "ship"
    assert result.human_review_needed is False


# --- Stop: an unresolved citation regenerates (≤3) then escalates ------------
@pytest.mark.asyncio
async def test_stop_regenerates_then_human_review(monkeypatch):
    case_id = str(uuid.uuid4())
    # Every generation cites a src_id that was never retrieved → never resolves.
    scripted = [_Resp([_text("Claim [ERISA §503, src_deadbeef] applies.")], "end_turn")]
    fake, _calls = _install(monkeypatch, scripted)

    async with AsyncSessionLocal() as s:
        result = await run_agent(
            model="m",
            system_blocks=[],
            tool_names=[],
            initial_user_message="go",
            case_file_id=case_id,
            actor="lead_planner",
            session=s,
        )
        await s.commit()

    assert result.stop_action == "human_review"
    assert result.human_review_needed is True
    # Three attempts total: regenerate, regenerate, then human_review.
    assert fake.messages.calls == 3
