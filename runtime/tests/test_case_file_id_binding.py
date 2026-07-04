"""Tenant binding (Phase 2.1 / DL-20): a case-scoped tool may act only on the run's
authorized case. The model chooses the case_file_id arg; pre_tool_use_hook enforces
equality with the server-pinned authorized case (PreToolUseInput.case_file_id)."""

from __future__ import annotations

from app.hooks.contracts import PreToolUseInput
from app.hooks.pre_tool_use import CASE_SCOPED_TOOLS, pre_tool_use_hook

AUTH = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


def _inp(tool_name: str, tool_args: dict, case_file_id: str = AUTH) -> PreToolUseInput:
    return PreToolUseInput(
        case_file_id=case_file_id, actor="bill_detective", tool_name=tool_name, tool_args=tool_args
    )


def test_matching_case_approved():
    assert pre_tool_use_hook(_inp("pg_case_file_get", {"case_file_id": AUTH})).approved is True


def test_cross_tenant_case_denied():
    r = pre_tool_use_hook(_inp("pg_case_file_get", {"case_file_id": OTHER}))
    assert r.approved is False
    assert OTHER in (r.block_reason or "")
    assert "tenant isolation" in (r.block_reason or "")


def test_missing_case_arg_denied():
    r = pre_tool_use_hook(_inp("pg_upsert_finding", {"finding_type": "payer_side"}))
    assert r.approved is False
    assert "no case_file_id" in (r.block_reason or "")


def test_freeform_run_denies_case_scoped_tool():
    # A freeform chat passes case_file_id="" — a case-scoped tool has no case context.
    r = pre_tool_use_hook(_inp("pg_case_file_get", {"case_file_id": AUTH}, case_file_id=""))
    assert r.approved is False
    assert "not bound to" in (r.block_reason or "")


def test_pg_list_due_requires_matching_case():
    # Omitting the optional case_file_id would list ALL cases' deadlines → deny.
    assert pre_tool_use_hook(_inp("pg_list_due", {"within_days": 30})).approved is False
    assert pre_tool_use_hook(_inp("pg_list_due", {"within_days": 30, "case_file_id": AUTH})).approved


def test_knowledge_tool_unaffected():
    assert pre_tool_use_hook(_inp("qdrant_search_billing_codes", {"query": "99213"})).approved


def test_all_case_scoped_tools_reject_cross_tenant():
    for tool in CASE_SCOPED_TOOLS:
        r = pre_tool_use_hook(_inp(tool, {"case_file_id": OTHER}))
        assert r.approved is False, f"{tool} allowed cross-tenant access"
