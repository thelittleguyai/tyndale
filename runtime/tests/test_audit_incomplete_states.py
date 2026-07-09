"""Honest audit_incomplete sub-states (HP-1, 2026-07-07).

A document-poor case (the Beloit shape: collections notice only, no EOB/bill) produced correct
partial findings but surfaced under the failure banner "we couldn't finish this audit — our team
has been notified." Wrong framing. The terminal reason is now persisted and split:
  needs_documents — user-actionable: findings/partial ran, three-number blocked on missing inputs
                    → positive screen + document checklist. No alert.
  system_error    — budget/citation/provider/crash → apology + a real, counted alert.
The reason is persisted so GET /v1/audit/{id} renders the same honest screen on re-fetch (the
bug was: get_audit always returned incomplete_reason=None)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import llm_health, runner
from app.agents.orchestrator import _assemble_result, _documents_needed, finalize_audit
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile


# --- pure checklist derivation: ask only for what's actually missing ---
def test_documents_needed_lists_only_whats_missing():
    poor = SimpleNamespace(documents=[{"document_type": "collections_notice"}], coverage=None)
    assert {d.key for d in _documents_needed(poor)} == {"eob", "itemized_bill", "sbc"}

    rich = SimpleNamespace(
        documents=[{"document_type": "eob"}, {"document_type": "bill"}],
        coverage={"deductible": {"total": 1000}},
    )
    assert _documents_needed(rich) == []


# --- fake Claude client: ships clean text, NO three-number tool call → audit stays None ---
class _Usage:
    input_tokens = output_tokens = 5


class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason, self.usage = content, stop_reason, _Usage()


class _Msgs:
    async def create(self, **kw):
        return _Resp([_Blk(type="text", text="Reviewed — nothing computable yet.")], "end_turn")


class _FakeClient:
    def __init__(self):
        self.messages = _Msgs()


def _force_real(monkeypatch, s):
    monkeypatch.setattr(s, "use_real_claude", True)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test-fake")
    monkeypatch.setattr(s, "litellm_proxy_url", None)


async def _doc_poor_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files={"file": ("collections.pdf", b"%PDF-1.4 final notice", "application/pdf")}
    )
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        cf.documents = [{"document_type": "collections_notice", "filename": "collections.pdf"}]
        cf.coverage = None
        await s.commit()
    return case_id


@pytest.mark.asyncio
async def test_needs_documents_is_honest_not_a_failure(client: AsyncClient, monkeypatch):
    case_id = await _doc_poor_case(client)
    s = get_settings()
    _force_real(monkeypatch, s)
    monkeypatch.setattr(s, "audit_wall_clock_budget_seconds", 600)  # budget is NOT the limiter
    monkeypatch.setattr(runner, "_client", lambda: _FakeClient())

    before = llm_health.system_alerts()["count"]
    result = await finalize_audit(case_id)

    assert result.status == "audit_incomplete"
    assert result.incomplete_reason == "needs_documents"  # NOT system_error
    assert {d.key for d in result.documents_needed} >= {"eob", "itemized_bill"}
    assert llm_health.system_alerts()["count"] == before  # a partial result is NOT an alert

    # Persisted, so the re-fetch renders the SAME honest screen (the original bug).
    async with AsyncSessionLocal() as sess:
        cf = (
            await sess.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert cf.audit_incomplete_reason == "needs_documents"
    refetch = await _assemble_result(case_id, composed="")
    assert refetch.incomplete_reason == "needs_documents"
    assert refetch.documents_needed  # checklist survives the re-fetch


@pytest.mark.asyncio
async def test_system_error_emits_a_real_counted_alert(client: AsyncClient, monkeypatch):
    case_id = await _doc_poor_case(client)
    s = get_settings()
    _force_real(monkeypatch, s)
    monkeypatch.setattr(s, "audit_wall_clock_budget_seconds", 0)  # cut short before any numbers
    monkeypatch.setattr(runner, "_client", lambda: _FakeClient())

    before = llm_health.system_alerts()["count"]
    result = await finalize_audit(case_id)

    assert result.status == "audit_incomplete"
    assert result.incomplete_reason == "system_error"
    assert result.documents_needed == []  # no checklist on a system error
    # "our team has been notified" is made TRUE — the alert is emitted + counted for admins.
    assert llm_health.system_alerts()["count"] == before + 1
