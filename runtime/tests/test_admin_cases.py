"""Phase CO-9 Module 3 — admin bill comparison: verdict v2, filters, export."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding


async def _dev_admin_id() -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _fresh_case(**fields) -> str:
    uid = await _dev_admin_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status=fields.pop("status", "open"), **fields)
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _add_finding(case_file_id: str) -> str:
    async with AsyncSessionLocal() as s:
        f = Finding(
            case_file_id=uuid.UUID(case_file_id),
            finding_type="payer_side",
            category="cost_sharing_miscalculation",
            subagent_source="math_person",
            voice_tier="A",
            facts={"gap": 120.0},
            status="open",
        )
        s.add(f)
        await s.commit()
        return str(f.finding_id)


async def _add_audit_event(case_file_id: str) -> None:
    async with AsyncSessionLocal() as s:
        s.add(
            AuditEvent(
                event_type="tool_invocation",
                actor="bill_detective",
                case_file_id=uuid.UUID(case_file_id),
                payload_encrypted=b'{"tool_result": {"ok": true}}',
                payload_hash=b"\x00" * 32,
                key_version=0,
                tools_invoked=["qdrant_search_payer_policies"],
                retrieved_chunks=[{"chunk_id": "ncd-220.4#1"}],
                outcome="success",
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_verdict_post_extended_options_writes_audit(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        f"/v1/admin/cases/{cfid}/verdict",
        json={"verdict": "missed_finding", "missed_findings": ["upcoding on 99214"], "notes": "x"},
    )
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as s:
        v = (
            await s.execute(
                select(AdminVerdict).where(
                    AdminVerdict.verdict_id == uuid.UUID(r.json()["verdict_id"])
                )
            )
        ).scalar_one()
    assert v.verdict == "missed_finding"
    assert v.missed_findings == ["upcoding on 99214"]
    async with AsyncSessionLocal() as s:
        audits = (
            (
                await s.execute(
                    select(AuditEvent)
                    .where(AuditEvent.case_file_id == uuid.UUID(cfid))
                    .where(AuditEvent.event_type == "user_action")
                )
            )
            .scalars()
            .all()
        )
    assert any(
        json.loads(bytes(a.payload_encrypted).decode()).get("action") == "verdict" for a in audits
    )


@pytest.mark.asyncio
async def test_list_cases_filters_by_verdict(client: AsyncClient):
    cfid = await _fresh_case()
    await client.post(f"/v1/admin/cases/{cfid}/verdict", json={"verdict": "hallucinated"})
    hits = (await client.get("/v1/admin/cases?verdict=hallucinated")).json()["cases"]
    assert any(c["case_file_id"] == cfid for c in hits)
    others = (await client.get("/v1/admin/cases?verdict=correct")).json()["cases"]
    assert all(c["case_file_id"] != cfid for c in others)


@pytest.mark.asyncio
async def test_case_detail_includes_reasoning_trail(client: AsyncClient):
    cfid = await _fresh_case(coverage={"deductible_amount": 2000})
    fid = await _add_finding(cfid)
    await _add_audit_event(cfid)
    detail = (await client.get(f"/v1/admin/cases/{cfid}")).json()
    assert any(f["finding_id"] == fid for f in detail["findings"])
    assert "user_feedback" in detail and "latest_verdict" in detail
    prov = (await client.get(f"/v1/admin/cases/{cfid}/provenance")).json()
    assert len(prov["tools_called"]) >= 1  # reasoning trail


@pytest.mark.asyncio
async def test_case_export_returns_full_json(client: AsyncClient):
    cfid = await _fresh_case(coverage={"deductible_amount": 2000})
    fid = await _add_finding(cfid)
    await _add_audit_event(cfid)
    await client.post(f"/v1/admin/cases/{cfid}/verdict", json={"verdict": "correct"})
    exp = (await client.get(f"/v1/admin/cases/{cfid}/export")).json()
    assert exp["case_file_id"] == cfid
    for key in ("documents", "coverage", "findings", "reasoning_trail", "feedback", "verdicts"):
        assert key in exp
    assert any(f["finding_id"] == fid for f in exp["findings"])
    assert len(exp["verdicts"]) >= 1
    assert len(exp["reasoning_trail"]) >= 1
