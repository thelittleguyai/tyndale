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


# What Brock's §7-2b requires of ANY disapproving verdict, on either route (deep review C3).
_SECTION_7_2B = {
    "scope": "whole_case",
    "cause": "reasoning_error",
    "structured_note": {
        "concluded": "no upcoding finding",
        "should_have_concluded": "99214 is upcoded against the documented complexity",
        "input_or_rule": "E/M level table",
    },
}


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
        json={
            "verdict": "missed_finding", "missed_findings": ["upcoding on 99214"], "notes": "x",
            **_SECTION_7_2B,
        },
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
    payloads = [json.loads(bytes(a.payload_encrypted).decode()) for a in audits]
    assert any(
        p.get("action") == "review_verdict" and p.get("via") == "legacy_cases_route"
        for p in payloads
    )


@pytest.mark.asyncio
async def test_list_cases_filters_by_verdict(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        f"/v1/admin/cases/{cfid}/verdict", json={"verdict": "hallucinated", **_SECTION_7_2B}
    )
    assert r.status_code == 200, r.text
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



# ══ deep review C3 (2026-09-18): the legacy route is a strict alias, not a bypass ════════════


@pytest.mark.asyncio
async def test_legacy_verdict_without_cause_scope_or_note_is_rejected(client: AsyncClient):
    cfid = await _fresh_case()
    for bare in ("missed_finding", "hallucinated", "partial", "wrong", "partially_correct"):
        r = await client.post(f"/v1/admin/cases/{cfid}/verdict", json={"verdict": bare, "notes": "x"})
        assert r.status_code == 422, (bare, r.text)
        detail = " ".join(r.json()["detail"])
        assert "cause" in detail and "scope" in detail and "structured_note" in detail
    async with AsyncSessionLocal() as s:
        written = (
            await s.execute(select(AdminVerdict).where(AdminVerdict.case_file_id == uuid.UUID(cfid)))
        ).scalars().all()
    assert written == []  # a rejected verdict leaves nothing behind


@pytest.mark.asyncio
async def test_legacy_verdicts_enter_the_review_state_machine_and_the_approval_rate(client: AsyncClient):
    """The approval rate is computed from case_reviews, so a verdict path that skipped it was
    invisible. Legacy approve / disapprove / can't-verify now each land there."""
    from app.db.models.case_reviews import CaseReview
    from app.review import queue as rq

    async with AsyncSessionLocal() as s:
        before = await rq.health(s)

    approved = await _fresh_case()
    r = await client.post(f"/v1/admin/cases/{approved}/verdict", json={"verdict": "correct", "notes": "ok"})
    assert r.status_code == 200 and r.json()["state"] == "approved" and r.json()["stored"] is True
    disapproved = await _fresh_case()
    r = await client.post(
        f"/v1/admin/cases/{disapproved}/verdict", json={"verdict": "wrong", **_SECTION_7_2B}
    )
    assert r.status_code == 200 and r.json()["state"] == "disapproved" and r.json()["cause"] == "reasoning_error"
    unverifiable = await _fresh_case()
    r = await client.post(f"/v1/admin/cases/{unverifiable}/verdict", json={"verdict": "unable_to_verify"})
    assert r.status_code == 200 and r.json()["state"] == "cant_verify"

    async with AsyncSessionLocal() as s:
        after = await rq.health(s)
        states = {}
        for cfid in (approved, disapproved, unverifiable):
            row = (
                await s.execute(select(CaseReview).where(CaseReview.case_file_id == uuid.UUID(cfid)))
            ).scalar_one()
            assert row.verdict_id is not None and row.reviewer_id is not None and row.decided_at is not None
            states[cfid] = row.state
    assert states == {approved: "approved", disapproved: "disapproved", unverifiable: "cant_verify"}
    assert after["approved_7d"] - before["approved_7d"] == 1
    assert after["disapproved_7d"] - before["disapproved_7d"] == 1  # cant_verify moved neither


def test_no_code_path_constructs_a_verdict_outside_the_service():
    """'Approval rate unaffected by any path that bypasses case_reviews' — enforced
    structurally: AdminVerdict( appears in exactly one module under app/."""
    import pathlib
    import re

    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = [
        str(f.relative_to(app_dir))
        for f in app_dir.rglob("*.py")
        if re.search(r"\bAdminVerdict\(", f.read_text(encoding="utf-8"))
        and f.name not in ("admin_verdicts.py",)
    ]
    assert offenders == ["review/verdicts.py"], offenders
