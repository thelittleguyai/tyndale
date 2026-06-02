"""Phase CO-9 Module 6 — knowledge gap log: tool + admin dashboard."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.db.models.knowledge_gap_log import KnowledgeGapLog
from app.tools.log_knowledge_gap import log_knowledge_gap


@pytest.mark.asyncio
async def test_log_knowledge_gap_inserts_row():
    # Synthetic call from each of the 3 subagents (confirmation f).
    ids = []
    for agent in ("lead_planner", "bill_detective", "math_person"):
        gid = await log_knowledge_gap(
            agent_name=agent,
            gap_type="no_data",
            query=f"{agent} needs an Aetna policy for 99214",
        )
        ids.append(gid)
    async with AsyncSessionLocal() as s:
        for gid in ids:
            row = (
                await s.execute(select(KnowledgeGapLog).where(KnowledgeGapLog.gap_id == gid))
            ).scalar_one()
            assert row.gap_type == "no_data"


@pytest.mark.asyncio
async def test_gap_aggregation_by_agent(client: AsyncClient):
    await log_knowledge_gap(agent_name="bill_detective", gap_type="no_data", query="agg by agent")
    r = await client.get("/v1/admin/knowledge-gaps/aggregate?group_by=agent")
    assert r.status_code == 200
    groups = {g["key"]: g["count"] for g in r.json()["groups"]}
    assert "bill_detective" in groups


@pytest.mark.asyncio
async def test_gap_aggregation_by_cluster_returns_top_20(client: AsyncClient):
    for _ in range(3):
        await log_knowledge_gap(
            agent_name="math_person",
            gap_type="self_reported",
            query="missing EOB allowed amount for cluster",
        )
    r = await client.get("/v1/admin/knowledge-gaps/aggregate?group_by=cluster")
    assert r.status_code == 200
    clusters = r.json()["clusters"]
    assert len(clusters) <= 20
    assert any(c["cluster"].startswith("missing eob allowed") for c in clusters)


@pytest.mark.asyncio
async def test_resolve_gap_sets_resolved_at_writes_audit(client: AsyncClient):
    gid = await log_knowledge_gap(
        agent_name="lead_planner",
        gap_type="low_confidence",
        query="resolve me",
        confidence_score=0.3,
    )
    r = await client.post(
        f"/v1/admin/knowledge-gaps/{gid}/resolve",
        json={"resolved_by_source": "CO-2B Aetna policies"},
    )
    assert r.status_code == 200
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(select(KnowledgeGapLog).where(KnowledgeGapLog.gap_id == gid))
        ).scalar_one()
        assert row.resolved_at is not None
        assert row.resolved_by_source == "CO-2B Aetna policies"
        audits = (
            (await s.execute(select(AuditEvent).where(AuditEvent.event_type == "user_action")))
            .scalars()
            .all()
        )
    payloads = [json.loads(bytes(a.payload_encrypted).decode()) for a in audits]
    assert any(p.get("action") == "resolve_knowledge_gap" for p in payloads)
