"""Audit wall-clock + regeneration budget (Item 1, 2026-07-06).

The empty-KB stall: the Lead Planner's cited summary fails Stop-hook citation resolution and
regenerates up to 3x, each a full multi-minute model pass. These tests lock: the regen loop
stops when the budget is spent; a budget-exceeded audit persists audit_incomplete
(budget_exceeded) and is NEVER left in audit_running; a clean/fast run is unaffected."""

from __future__ import annotations

import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import runner
from app.agents.audit_budget import AuditBudget, reset_audit_budget, set_audit_budget
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile


class _Usage:
    input_tokens = 5
    output_tokens = 5


class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason, self.usage = content, stop_reason, _Usage()


def _text_resp(text: str):
    return _Resp([_Blk(type="text", text=text)], "end_turn")


class _FakeMessages:
    def __init__(self, text, raises=False):
        self.calls = 0
        self._text = text
        self._raises = raises

    async def create(self, **kw):
        self.calls += 1
        if self._raises:
            raise RuntimeError("provider boom")
        return _text_resp(self._text)


class _FakeClient:
    def __init__(self, text="All set — nothing to dispute.", raises=False):
        self.messages = _FakeMessages(text, raises)


# Output carrying an UNRESOLVED citation → the Stop gate asks to regenerate every attempt.
_UNRESOLVED = "You may be owed a refund [NSA §300gg-111, src_deadbeef]."


# --- pure budget primitive ---
def test_budget_take_regen_caps_and_expires():
    b = AuditBudget(deadline=time.monotonic() + 10, regen_remaining=2)
    assert [b.take_regen(), b.take_regen(), b.take_regen()] == [True, True, False]
    assert b.regens_used == 2
    spent = AuditBudget(deadline=time.monotonic() - 1, regen_remaining=5)
    assert spent.take_regen() is False
    assert spent.expired() is True


async def _run_lead_planner(fake) -> runner.RunResult:
    return await runner.run_agent(
        model="claude-test",
        system_blocks=[],
        tool_names=[],
        initial_user_message="compose the audit summary",
        case_file_id=str(uuid.uuid4()),
        actor="lead_planner",
    )


# --- the regen loop respects the budget ---
@pytest.mark.asyncio
async def test_regen_loop_stops_when_regen_budget_spent(monkeypatch):
    fake = _FakeClient(_UNRESOLVED)
    monkeypatch.setattr(runner, "_client", lambda: fake)
    budget = AuditBudget(deadline=time.monotonic() + 30, regen_remaining=0)  # no regens allowed
    token = set_audit_budget(budget)
    try:
        res = await _run_lead_planner(fake)
    finally:
        reset_audit_budget(token)
    assert fake.messages.calls == 1  # one attempt, no regeneration
    assert res.budget_stopped is True


@pytest.mark.asyncio
async def test_regen_loop_runs_all_attempts_without_a_budget(monkeypatch):
    # Control: the SAME unresolved output regenerates up to max_attempts (3) with no budget.
    fake = _FakeClient(_UNRESOLVED)
    monkeypatch.setattr(runner, "_client", lambda: fake)
    res = await _run_lead_planner(fake)
    assert fake.messages.calls == 3
    assert res.budget_stopped is False


@pytest.mark.asyncio
async def test_clean_run_unaffected_by_budget(monkeypatch):
    # A grounded (no-citation) output ships on attempt 1 — a budget in place changes nothing.
    fake = _FakeClient("This bill checks out — nothing to dispute.")
    monkeypatch.setattr(runner, "_client", lambda: fake)
    budget = AuditBudget(deadline=time.monotonic() + 30, regen_remaining=3)
    token = set_audit_budget(budget)
    try:
        res = await _run_lead_planner(fake)
    finally:
        reset_audit_budget(token)
    assert fake.messages.calls == 1
    assert res.budget_stopped is False
    assert res.stop_action == "ship"


# --- orchestrator: budget-exceeded terminal + never-stuck ---
async def _fresh_case(client: AsyncClient) -> str:
    up = await client.post("/v1/upload", files={"file": ("bill.txt", b"sample bill", "text/plain")})
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


def _force_real(monkeypatch, settings):
    monkeypatch.setattr(settings, "use_real_claude", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(settings, "litellm_proxy_url", None)


@pytest.mark.asyncio
async def test_finalize_budget_exceeded_persists_incomplete(client: AsyncClient, monkeypatch):
    from app.agents.orchestrator import finalize_audit
    from app.config import get_settings

    case_id = await _fresh_case(client)
    s = get_settings()
    _force_real(monkeypatch, s)
    monkeypatch.setattr(s, "audit_wall_clock_budget_seconds", 0)  # deadline immediately past
    monkeypatch.setattr(runner, "_client", lambda: _FakeClient())

    result = await finalize_audit(case_id)
    assert result.status == "audit_incomplete"
    assert result.incomplete_reason == "budget_exceeded"
    # Never left stuck in audit_running.
    async with AsyncSessionLocal() as sess:
        cf = (
            await sess.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert cf.status == "audit_incomplete"


@pytest.mark.asyncio
async def test_finalize_never_leaves_audit_running_on_error(client: AsyncClient, monkeypatch):
    from app.agents.orchestrator import finalize_audit
    from app.config import get_settings

    case_id = await _fresh_case(client)
    s = get_settings()
    _force_real(monkeypatch, s)
    monkeypatch.setattr(runner, "_client", lambda: _FakeClient(raises=True))

    with pytest.raises(Exception):
        await finalize_audit(case_id)
    async with AsyncSessionLocal() as sess:
        cf = (
            await sess.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert cf.status == "audit_incomplete"  # not stuck in audit_running
