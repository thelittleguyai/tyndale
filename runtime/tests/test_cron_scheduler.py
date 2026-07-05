"""Scheduled cron execution (Phase 3.2 / 3.3): the `python -m app.crons <name>` entrypoint
records CronRunLog (so the admin console's real last-run panel reflects scheduled runs), and the
qdrant_snapshot cron no-ops cleanly when Qdrant is off-server (local/embedded)."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.cron_run_log import CronRunLog

cron_main = importlib.import_module("app.crons.__main__")


@pytest.mark.asyncio
async def test_scheduled_run_records_cron_run_log():
    rc = await cron_main.run_cron("noop")
    assert rc == 0
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CronRunLog)
                .where(CronRunLog.cron_name == "noop")
                .order_by(CronRunLog.started_at.desc())
                .limit(1)
            )
        ).scalar_one()
    assert row.status == "success"
    assert row.triggered_source == "scheduled"
    assert row.finished_at is not None
    assert row.summary_json == {"ok": True, "noop": True}


@pytest.mark.asyncio
async def test_unknown_cron_returns_error_and_writes_no_row():
    rc = await cron_main.run_cron("does_not_exist_xyz")
    assert rc == 1
    async with AsyncSessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(CronRunLog).where(CronRunLog.cron_name == "does_not_exist_xyz")
                )
            )
            .scalars()
            .all()
        )
    assert rows == []


@pytest.mark.asyncio
async def test_qdrant_snapshot_skips_off_server(monkeypatch):
    from app.crons import qdrant_snapshot_cron as qs

    monkeypatch.setattr(qs, "is_server_mode", lambda: False)
    result = await qs.run_qdrant_snapshot_cron()
    assert "skipped" in result
