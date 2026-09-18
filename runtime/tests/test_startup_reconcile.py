"""Startup reconciliation sweep (Item 12, 2026-07-06).

A SIGKILL / deploy roll / OOM strands rows in a non-terminal 'running' state — the frontend
polls a dead audit forever, the cron history shows a run that never ended. On boot,
reconcile_interrupted_runs() flips ones that provably cannot still be running to a terminal
state: case_files audit_running -> audit_incomplete, cron_run_log 'running' -> 'interrupted'.
The age guard spares work that could still be in flight on a concurrent replica.

These lock: stale rows flip while recent ones are spared; computed partials survive the flip;
a boot invokes the sweep exactly once; and the sweep never raises (startup must not fail on a
reconciliation error)."""

from __future__ import annotations

import datetime
import pathlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.cron_run_log import CronRunLog
from app.startup_reconcile import reconcile_interrupted_runs


def _ago(**kw) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(**kw)


async def _fresh_case(client: AsyncClient) -> uuid.UUID:
    up = await client.post(
        "/v1/upload", files={"file": ("bill.txt", b"%PDF-1.4 sample bill", "text/plain")}
    )
    assert up.status_code == 200, up.text
    return uuid.UUID(up.json()["case_file_id"])


@pytest.mark.asyncio
async def test_reconcile_flips_stale_and_spares_recent(client: AsyncClient):
    stale_case = await _fresh_case(client)
    recent_case = await _fresh_case(client)

    async with AsyncSessionLocal() as s:
        # stale: went audit_running well beyond budget+buffer ago -> can't still be running.
        # recent: 1 min ago -> could still be live on another replica, must be spared. DB-side
        # now() dodges clock skew; raw SQL bypasses the ORM onupdate so the timestamps stick.
        await s.execute(
            text(
                "UPDATE case_files SET status='audit_running', "
                "updated_at = now() - interval '30 minutes' WHERE case_file_id = :id"
            ),
            {"id": str(stale_case)},
        )
        await s.execute(
            text(
                "UPDATE case_files SET status='audit_running', "
                "updated_at = now() - interval '1 minute' WHERE case_file_id = :id"
            ),
            {"id": str(recent_case)},
        )
        stale_cron = CronRunLog(
            cron_name="tyndale-dev-cron-hospital-mrf",
            status="running",
            triggered_source="scheduled",
            started_at=_ago(hours=10),  # older than the 6h cron ceiling
        )
        recent_cron = CronRunLog(
            cron_name="tyndale-dev-cron-nudges",
            status="running",
            triggered_source="scheduled",
            started_at=_ago(minutes=2),  # a job that just started
        )
        s.add_all([stale_cron, recent_cron])
        await s.commit()
        stale_cron_id, recent_cron_id = stale_cron.run_id, recent_cron.run_id

    result = await reconcile_interrupted_runs()
    assert result["audits"] >= 1 and result["crons"] >= 1

    async with AsyncSessionLocal() as s:
        assert (await s.get(CaseFile, stale_case)).status == "audit_incomplete"
        assert (await s.get(CaseFile, recent_case)).status == "audit_running"  # spared by age guard
        sc = await s.get(CronRunLog, stale_cron_id)
        assert sc.status == "interrupted"
        assert sc.finished_at is not None
        assert sc.error_message  # a reconciliation note is recorded
        assert (await s.get(CronRunLog, recent_cron_id)).status == "running"  # spared


@pytest.mark.asyncio
async def test_reconcile_keeps_partials(client: AsyncClient):
    case = await _fresh_case(client)
    async with AsyncSessionLocal() as s:
        cf = await s.get(CaseFile, case)
        cf.status = "audit_running"
        cf.plan_current = {"summary": "partial work computed before the kill"}
        # Explicitly setting updated_at suppresses the onupdate=now() so the row reads as stale.
        cf.updated_at = _ago(minutes=30)
        await s.commit()

    await reconcile_interrupted_runs()

    async with AsyncSessionLocal() as s:
        cf = await s.get(CaseFile, case)
        assert cf.status == "audit_incomplete"  # flipped to terminal
        assert cf.plan_current == {"summary": "partial work computed before the kill"}  # kept


@pytest.mark.asyncio
async def test_boot_invokes_reconcile(monkeypatch):
    import app.main as main_module

    called = {"n": 0}

    async def _spy(*_a, **_k):
        called["n"] += 1
        return {"audits": 0, "crons": 0}

    monkeypatch.setattr(main_module, "reconcile_interrupted_runs", _spy)
    async with main_module.lifespan(main_module.app):  # run the real startup/shutdown sequence
        pass
    assert called["n"] == 1  # the sweep runs exactly once on boot


@pytest.mark.asyncio
async def test_reconcile_never_raises_on_failure():
    def _boom():
        raise RuntimeError("db unreachable at boot")

    # A failing session factory must be swallowed — startup continues regardless.
    result = await reconcile_interrupted_runs(session_factory=_boom)
    assert result == {"audits": 0, "crons": 0}


@pytest.mark.asyncio
async def test_reconciled_audit_is_system_error_through_the_chokepoint(client: AsyncClient):
    """2026-09-18: a deploy-killed audit used to be flipped with a bare UPDATE — no reason, so
    the result assembler defaulted to needs_documents (the user was asked for documents for
    OUR failure), and nothing downstream (thread, lifecycle event, review queue) fired. Now the
    flip carries system_error and goes through _set_status, so the review queue sees it."""
    from sqlalchemy import select

    from app.db.models.case_reviews import CaseReview
    from app.review import queue as review_queue

    from app.auth.dev_user import resolve_dev_user

    async def _dial(pct: int) -> None:
        async with AsyncSessionLocal() as s:
            admin = await resolve_dev_user(s)
            await review_queue.set_sample_pct(s, pct, admin_id=admin.user_id)
            await s.commit()

    await _dial(0)
    try:
        cfid = await _fresh_case(client)
        async with AsyncSessionLocal() as s:
            await s.execute(
                text(
                    "UPDATE case_files SET status='audit_running', "
                    "updated_at = now() - interval '1 hour' WHERE case_file_id = :id"
                ),
                {"id": str(cfid)},
            )
            await s.commit()
        result = await reconcile_interrupted_runs()
        assert result["audits"] >= 1
        async with AsyncSessionLocal() as s:
            cf = await s.get(CaseFile, cfid)
            assert cf.status == "audit_incomplete"
            assert cf.audit_incomplete_reason == "system_error"
            row = (
                await s.execute(select(CaseReview).where(CaseReview.case_file_id == cfid))
            ).scalar_one()
        # dial at 0 — only the system_error TRIGGER can have enqueued it
        assert row.system_error and "system_error" in row.triggers and not row.sampled
        assert row.terminal_status == "audit_incomplete" and row.incomplete_reason == "system_error"
    finally:
        await _dial(100)


def test_stuck_audits_cron_is_registered_and_scheduled():
    """The sweep also runs on a schedule — the boot-only version left a case stranded until
    the next deploy (two e2e sweep cases on dev, 2026-09-18)."""
    from app.crons.registry import CRON_REGISTRY, get_cron

    assert "stuck_audits" in CRON_REGISTRY and get_cron("stuck_audits") is not None
    tf = (pathlib.Path(__file__).resolve().parents[2] / "infra/envs/dev/crons.tf").read_text()
    assert 'stuck_audits = { cron = "*/15 * * * *"' in tf
