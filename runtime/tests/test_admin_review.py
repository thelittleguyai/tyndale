"""Human Review Phase 1 — the admin review API (doc 39 §1–§2 as amended by §7): queue +
health strip, the dial, the four-tab workspace (with its view audit event), and the three
verdict actions with their validation."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.review import queue as rq


async def _dev_admin_id() -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _set_dial(pct: int) -> None:
    async with AsyncSessionLocal() as s:
        await rq.set_sample_pct(s, pct, admin_id=await _dev_admin_id())
        await s.commit()


async def _case(**fields) -> str:
    uid = await _dev_admin_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status=fields.pop("status", "audit_complete"), **fields)
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _finding(case_file_id: str, **over) -> str:
    async with AsyncSessionLocal() as s:
        f = Finding(
            case_file_id=uuid.UUID(case_file_id),
            finding_type=over.get("finding_type", "provider_side"),
            category=over.get("category", "bundling"),
            subagent_source="bill_detective",
            voice_tier="B",
            facts=over.get(
                "facts",
                {"gap": 120.0, "notes": "99284 billed alongside its component", "codes": ["99284"]},
            ),
            legal_claim=over.get(
                "legal_claim",
                {"claim": "NCCI bundles the component into the primary code.", "citations": []},
            ),
            recommendation=over.get(
                "recommendation",
                {"action": "Ask billing to remove the bundled line.", "reasoning": "NCCI edit"},
            ),
            status="open",
        )
        s.add(f)
        await s.commit()
        return str(f.finding_id)


async def _enqueued(**fields) -> tuple[str, str]:
    await _set_dial(100)
    cfid = await _case(**fields)
    rid = await rq.on_terminal(cfid, "audit_complete", None)
    assert rid
    return cfid, rid


async def _audit_actions(cfid: str) -> list[str]:
    async with AsyncSessionLocal() as s:
        rows = (
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
    return [json.loads(bytes(a.payload_encrypted).decode()).get("action") for a in rows]


_DISAPPROVE = {
    "action": "disapprove",
    "verdict_type": "missed_finding",
    "scope": "whole_case",
    "cause": "content_gap",
    "structured_note": {
        "concluded": "no finding on the bundled line",
        "should_have_concluded": "NCCI bundling finding",
        "input_or_rule": "ncci edit table missing the 99284 pair",
    },
}


# ── queue ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_lists_run_with_masked_user_and_health(client: AsyncClient):
    cfid, rid = await _enqueued()
    r = await client.get(
        "/v1/admin/review/queue", params={"state": "unreviewed,re_review,in_review", "limit": 200}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    item = next(i for i in body["items"] if i["review_id"] == rid)
    assert item["case_file_id"] == cfid and item["state"] == "unreviewed"
    assert item["user_masked"].startswith("u·") and len(item["user_masked"]) == 6
    assert "email" not in item and "user_id" not in item
    assert set(item["flags"]) == {"first_case", "system_error", "canary", "material_disagreement"}
    h = body["health"]
    for k in (
        "unreviewed",
        "in_review",
        "median_age_hours",
        "approval_rate_7d",
        "approval_rate_30d",
    ):
        assert k in h


@pytest.mark.asyncio
async def test_queue_filters_and_rejects_unknown_values(client: AsyncClient):
    assert (
        await client.get("/v1/admin/review/queue", params={"state": "bogus"})
    ).status_code == 422
    assert (
        await client.get("/v1/admin/review/queue", params={"confidence": "sky-high"})
    ).status_code == 422
    cfid = await _case(status="audit_incomplete", audit_incomplete_reason="system_error")
    rid = await rq.on_terminal(cfid, "audit_incomplete", "system_error")
    hits = (
        await client.get(
            "/v1/admin/review/queue", params={"has_system_error": "true", "limit": 200}
        )
    ).json()["items"]
    assert any(i["review_id"] == rid for i in hits)
    misses = (
        await client.get(
            "/v1/admin/review/queue", params={"has_system_error": "false", "limit": 200}
        )
    ).json()["items"]
    assert all(i["review_id"] != rid for i in misses)


@pytest.mark.asyncio
async def test_settings_dial_roundtrip(client: AsyncClient):
    try:
        assert (await client.get("/v1/admin/review/settings")).json()["review_sample_pct"] in range(
            0, 101
        )
        assert (
            await client.put("/v1/admin/review/settings", json={"review_sample_pct": 40})
        ).status_code == 200
        got = (await client.get("/v1/admin/review/settings")).json()
        assert got["review_sample_pct"] == 40 and set(got["triggers"]) == {
            "first_case",
            "low_confidence",
            "system_error",
            "canary",
            "material_disagreement",
        }
        assert (
            await client.put("/v1/admin/review/settings", json={"review_sample_pct": 101})
        ).status_code == 422
    finally:
        await _set_dial(100)
