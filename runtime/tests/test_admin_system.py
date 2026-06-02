"""Phase CO-9 Module 5 — admin system health + cron control tests."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.db.models.cron_run_log import CronRunLog


@pytest.mark.asyncio
async def test_system_health_returns_all_status_fields(client: AsyncClient):
    r = await client.get("/v1/admin/system/health")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "deploy_sha",
        "db_pool",
        "qdrant_status",
        "anthropic_status",
        "recent_errors",
        "runtime_version",
    ):
        assert key in body


@pytest.mark.asyncio
async def test_cron_trigger_writes_cron_run_log(client: AsyncClient):
    r = await client.post("/v1/admin/crons/noop/trigger")
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    run_id = r.json()["run_id"]
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(select(CronRunLog).where(CronRunLog.run_id == uuid.UUID(run_id)))
        ).scalar_one()
    assert row.cron_name == "noop"
    assert row.triggered_source == "manual_admin"
    assert row.triggered_by is not None


@pytest.mark.asyncio
async def test_cron_trigger_writes_audit_log(client: AsyncClient):
    r = await client.post("/v1/admin/crons/noop/trigger")
    run_id = r.json()["run_id"]
    async with AsyncSessionLocal() as s:
        audits = (
            (await s.execute(select(AuditEvent).where(AuditEvent.event_type == "user_action")))
            .scalars()
            .all()
        )
    payloads = [json.loads(bytes(a.payload_encrypted).decode()) for a in audits]
    assert any(p.get("action") == "cron_trigger" and p.get("run_id") == run_id for p in payloads)


@pytest.mark.asyncio
async def test_cron_runs_history_paginates(client: AsyncClient):
    await client.post("/v1/admin/crons/noop/trigger")
    await client.post("/v1/admin/crons/noop/trigger")
    r = await client.get("/v1/admin/crons/noop/runs?limit=1")
    assert r.status_code == 200
    assert len(r.json()["runs"]) == 1
    assert r.json()["cron_name"] == "noop"


@pytest.mark.asyncio
async def test_unknown_cron_trigger_returns_404(client: AsyncClient):
    r = await client.post("/v1/admin/crons/does_not_exist/trigger")
    assert r.status_code == 404
