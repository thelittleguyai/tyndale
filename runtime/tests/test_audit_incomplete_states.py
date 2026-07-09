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
from app.agents.orchestrator import (
    _assemble_result,
    _documents_needed,
    documents_all_satisfied,
    finalize_audit,
)
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile


# --- checklist derivation: the full 3-item checklist, each with a real have/need flag ---
def test_documents_needed_flags_have_per_item():
    # Nothing useful yet (a collections notice only) → all three items present, all unchecked.
    poor = SimpleNamespace(documents=[{"document_type": "collections_notice"}], coverage=None)
    poor_needs = _documents_needed(poor)
    assert {d.key for d in poor_needs} == {"eob", "itemized_bill", "sbc"}
    assert all(not d.have for d in poor_needs)
    assert not documents_all_satisfied(poor)

    # Everything present → still the full checklist, but all checked (and re-run is unblocked).
    rich = SimpleNamespace(
        documents=[{"document_type": "eob"}, {"document_type": "bill"}],
        coverage={"deductible": {"total": 1000}},
    )
    rich_needs = _documents_needed(rich)
    assert {d.key for d in rich_needs} == {"eob", "itemized_bill", "sbc"}
    assert all(d.have for d in rich_needs)
    assert documents_all_satisfied(rich)

    # A plan_summary document satisfies the SBC need even without structured coverage extracted yet.
    partial = SimpleNamespace(
        documents=[{"document_type": "eob"}, {"document_type": "plan_summary"}], coverage=None,
    )
    assert {d.key: d.have for d in _documents_needed(partial)} == {
        "eob": True, "itemized_bill": False, "sbc": True,
    }


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


async def _needs_documents_case(client: AsyncClient, *, documents, coverage) -> str:
    """A case pinned to audit_incomplete/needs_documents with a given inventory."""
    up = await client.post(
        "/v1/upload", files={"file": ("seed.pdf", b"%PDF-1.4 x", "application/pdf")}
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        cf.status = "audit_incomplete"
        cf.audit_incomplete_reason = "needs_documents"
        cf.documents = documents
        cf.coverage = coverage
        await s.commit()
    return case_id


def _ocr_returning(text: str):
    async def _ocr(args):
        return {
            "filename": args.get("filename", "f"), "ocr_text": text,
            "extraction_status": "extracted", "byte_count": 10, "pages": [],
            "key_value_pairs": [], "tables_count": 0,
        }

    return _ocr


@pytest.mark.asyncio
async def test_upload_completing_needs_documents_reruns_audit(client: AsyncClient, monkeypatch):
    # Blocked only on the EOB (bill + coverage already present). Adding the EOB completes the set.
    case_id = await _needs_documents_case(
        client, documents=[{"document_type": "bill"}], coverage={"deductible": {"total": 1000}}
    )
    monkeypatch.setattr("app.routes.upload.run_document_ocr", _ocr_returning("EXPLANATION OF BENEFITS"))
    calls: list[str] = []

    async def _spy(cfid):
        calls.append(cfid)

    monkeypatch.setattr("app.routes.upload.finalize_audit", _spy)

    r = await client.post(
        "/v1/upload", data={"case_file_id": case_id},
        files=[("files", ("eob.pdf", b"%PDF-1.4 x", "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    assert calls == [case_id]  # all inputs satisfied → audit re-run triggered


@pytest.mark.asyncio
async def test_upload_not_completing_set_does_not_rerun(client: AsyncClient, monkeypatch):
    # Still missing the itemized bill + SBC after adding just the EOB → no re-run.
    case_id = await _needs_documents_case(client, documents=[], coverage=None)
    monkeypatch.setattr("app.routes.upload.run_document_ocr", _ocr_returning("EXPLANATION OF BENEFITS"))
    calls: list[str] = []

    async def _spy(cfid):
        calls.append(cfid)

    monkeypatch.setattr("app.routes.upload.finalize_audit", _spy)

    r = await client.post(
        "/v1/upload", data={"case_file_id": case_id},
        files=[("files", ("eob.pdf", b"%PDF-1.4 x", "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    assert calls == []  # set incomplete → audit not re-run
