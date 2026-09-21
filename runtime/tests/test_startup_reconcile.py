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
        # stale: no heartbeat (a pre-heartbeat row) and updated_at far beyond the threshold
        # (max(3 x budget, 30 min)) -> can't still be running.
        # recent: 1 min ago -> could still be live on another replica, must be spared. DB-side
        # now() dodges clock skew; raw SQL bypasses the ORM onupdate so the timestamps stick.
        await s.execute(
            text(
                "UPDATE case_files SET status='audit_running', "
                "updated_at = now() - interval '3 hours' WHERE case_file_id = :id"
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

    result = await reconcile_interrupted_runs(only_case_ids={stale_case, recent_case})
    assert result["audits"] == 1 and result["crons"] >= 1

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
        cf.updated_at = _ago(hours=3)
        await s.commit()

    await reconcile_interrupted_runs(only_case_ids={case})

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
    assert result["audits"] == 0 and result["crons"] == 0


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
        result = await reconcile_interrupted_runs(only_case_ids={cfid})
        assert result["audits"] == 1
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


class _BrokenSession:
    """A session whose first statement dies with the connection (dev 2026-09-18 18:13)."""

    async def __aenter__(self):
        from sqlalchemy.exc import InterfaceError

        raise InterfaceError("stmt", {}, ConnectionError("connection was closed"))

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_claim_retries_a_broken_connection_then_sweeps(client: AsyncClient):
    """The boot sweep used to skip everything until the next boot when its first statement
    lost the connection. A broken connection is retried on a fresh session; the sweep
    still completes."""
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
    calls = {"n": 0}
    slept: list[float] = []

    def factory():
        calls["n"] += 1
        return _BrokenSession() if calls["n"] == 1 else AsyncSessionLocal()

    async def fake_sleep(s: float) -> None:
        slept.append(s)

    result = await reconcile_interrupted_runs(
        session_factory=factory, sleep=fake_sleep, only_case_ids={cfid}
    )
    assert result["audits"] == 1 and calls["n"] >= 2 and slept == [2.0]
    async with AsyncSessionLocal() as s:
        assert (await s.get(CaseFile, cfid)).status == "audit_incomplete"


@pytest.mark.asyncio
async def test_claim_gives_up_after_the_last_attempt_without_raising():
    async def fake_sleep(_s: float) -> None:
        return None

    result = await reconcile_interrupted_runs(session_factory=_BrokenSession, sleep=fake_sleep)
    assert result["audits"] == 0 and result["crons"] == 0  # logged + swallowed — boot never fails


# ══ deep review C2 (2026-09-18): the healer must never clobber a live or completed audit ═════


async def _strand(cfid: uuid.UUID, *, beat: str | None = "3 hours", updated: str = "3 hours") -> None:
    """Put a case in audit_running with a chosen heartbeat / updated_at age (raw SQL so the ORM
    onupdate can't refresh the timestamps)."""
    beat_sql = "NULL" if beat is None else f"now() - interval '{beat}'"
    async with AsyncSessionLocal() as s:
        await s.execute(
            text(
                "UPDATE case_files SET status='audit_running', audit_incomplete_reason=NULL, "
                f"audit_heartbeat_at = {beat_sql}, updated_at = now() - interval '{updated}', "
                "reconcile_token=NULL, reconcile_claimed_at=NULL, reconcile_attempts=0 "
                "WHERE case_file_id = :id"
            ),
            {"id": str(cfid)},
        )
        await s.commit()


async def _row(cfid: uuid.UUID) -> CaseFile:
    async with AsyncSessionLocal() as s:
        return await s.get(CaseFile, cfid)


async def _system_error_reviews(cfid: uuid.UUID) -> int:
    from sqlalchemy import func, select

    from app.db.models.case_reviews import CaseReview

    async with AsyncSessionLocal() as s:
        return (
            await s.execute(
                select(func.count())
                .select_from(CaseReview)
                .where(CaseReview.case_file_id == cfid, CaseReview.system_error.is_(True))
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_race_a_completed_audit_survives_the_healer(client: AsyncClient):
    """THE defect: claim, then the live replica finishes, then the follow-up. The follow-up is
    a compare-and-swap now — audit_complete stays, nothing is projected, nothing is enqueued as
    a system_error, and the healer reports a lost race instead of an apology card."""
    from app.agents import orchestrator

    cfid = await _fresh_case(client)
    await _strand(cfid)

    async def other_replica_completes(cid):
        assert (await _row(cid)).reconcile_token is not None  # the claim is on the row
        assert await orchestrator._set_status(str(cid), "audit_complete")  # owner's own write

    result = await reconcile_interrupted_runs(
        only_case_ids={cfid}, _after_claim=other_replica_completes
    )
    assert result["lost_race"] == 1 and result["audits"] == 0
    cf = await _row(cfid)
    assert cf.status == "audit_complete" and cf.audit_incomplete_reason is None
    assert cf.reconcile_token is None and cf.reconcile_claimed_at is None
    assert await _system_error_reviews(cfid) == 0


@pytest.mark.asyncio
async def test_set_status_guards_refuse_without_side_effects(client: AsyncClient, monkeypatch):
    from app.agents import orchestrator

    fired: list[str] = []

    async def spy(case_file_id, status, *a, **k):
        fired.append(status)

    monkeypatch.setattr(orchestrator, "_status_side_effects", spy)
    cfid = await _fresh_case(client)
    assert await orchestrator._set_status(str(cfid), "audit_complete")  # unconditional, as ever
    assert fired == ["audit_complete"]

    refused = await orchestrator._set_status(
        str(cfid), "audit_incomplete", incomplete_reason="system_error", expected_status="audit_running"
    )
    assert refused is False and fired == ["audit_complete"]  # nothing written, nothing fired
    assert (await _row(cfid)).status == "audit_complete"

    await _strand(cfid)
    wrong_token = await orchestrator._set_status(
        str(cfid), "audit_incomplete", incomplete_reason="system_error",
        expected_status="audit_running", expected_reconcile_token=uuid.uuid4(),
    )
    assert wrong_token is False and (await _row(cfid)).status == "audit_running"


@pytest.mark.asyncio
async def test_partial_batch_timeout_leaves_the_rest_re_pickable(client: AsyncClient):
    """Rows are claimed ONE AT A TIME: when the sweep budget runs out, the remainder is still
    audit_running and unclaimed — the next sweep picks it up. (The old claim-all-then-loop left
    a timed-out backlog flipped with no projection / lifecycle / enqueue, never re-picked.)"""
    a, b, c = [await _fresh_case(client) for _ in range(3)]
    await _strand(a, beat="5 hours")  # oldest first
    await _strand(b, beat="4 hours")
    await _strand(c, beat="3 hours")
    ticks = iter([0.0, 0.0, 10_000.0, 10_000.0, 10_000.0])

    first = await reconcile_interrupted_runs(
        only_case_ids={a, b, c}, budget_seconds=240.0, clock=lambda: next(ticks)
    )
    assert first["audits"] == 1 and first["deferred"] == 2
    assert (await _row(a)).status == "audit_incomplete"
    for untouched in (b, c):
        cf = await _row(untouched)
        assert cf.status == "audit_running" and cf.reconcile_token is None and cf.reconcile_attempts == 0

    second = await reconcile_interrupted_runs(only_case_ids={a, b, c})
    assert second["audits"] == 2 and second["deferred"] == 0
    assert {(await _row(x)).status for x in (a, b, c)} == {"audit_incomplete"}


@pytest.mark.asyncio
async def test_heartbeat_keeps_a_slow_live_audit_unhealed(client: AsyncClient):
    """updated_at is hours old (nothing refreshes it mid-run) but the orchestrator beat a minute
    ago — the audit is alive. Once the beat itself is older than the threshold, it is dead."""
    from app.agents import orchestrator

    cfid = await _fresh_case(client)
    await _strand(cfid, beat="1 minute", updated="3 hours")
    assert (await reconcile_interrupted_runs(only_case_ids={cfid}))["audits"] == 0
    assert (await _row(cfid)).status == "audit_running"

    # the orchestrator's beat refreshes ONLY a running case, and leaves updated_at alone
    await _strand(cfid, beat="2 hours", updated="3 hours")
    before = await _row(cfid)
    await orchestrator._heartbeat(str(cfid))
    after = await _row(cfid)
    assert after.audit_heartbeat_at > before.audit_heartbeat_at and after.updated_at == before.updated_at
    assert (await reconcile_interrupted_runs(only_case_ids={cfid}))["audits"] == 0

    done = await _fresh_case(client)
    await orchestrator._heartbeat(str(done))  # not running -> no beat is written
    assert (await _row(done)).audit_heartbeat_at is None

    await _strand(cfid, beat="2 hours", updated="1 minute")  # a fresh updated_at proves nothing
    assert (await reconcile_interrupted_runs(only_case_ids={cfid}))["audits"] == 1


@pytest.mark.asyncio
async def test_going_running_starts_the_heartbeat_and_resets_the_healer_state(client: AsyncClient):
    from app.agents import orchestrator

    cfid = await _fresh_case(client)
    async with AsyncSessionLocal() as s:
        await s.execute(
            text("UPDATE case_files SET reconcile_attempts=2, reconcile_token=gen_random_uuid(), "
                 "reconcile_claimed_at=now() WHERE case_file_id=:id"),
            {"id": str(cfid)},
        )
        await s.commit()
    await orchestrator._set_status(str(cfid), "audit_running")
    cf = await _row(cfid)
    assert cf.audit_heartbeat_at is not None and cf.reconcile_attempts == 0 and cf.reconcile_token is None


@pytest.mark.asyncio
async def test_dead_audit_is_healed_once_and_idempotently(client: AsyncClient):
    cfid = await _fresh_case(client)
    await _strand(cfid)
    first = await reconcile_interrupted_runs(only_case_ids={cfid})
    assert first["audits"] == 1
    cf = await _row(cfid)
    assert (cf.status, cf.audit_incomplete_reason) == ("audit_incomplete", "system_error")
    assert cf.reconcile_token is None and cf.reconcile_attempts == 1
    reviews = await _system_error_reviews(cfid)

    again = await reconcile_interrupted_runs(only_case_ids={cfid})
    assert again["audits"] == 0 and again["replayed"] == 0 and again["failed"] == 0
    assert (await _row(cfid)).reconcile_attempts == 1
    assert await _system_error_reviews(cfid) == reviews  # no second enqueue, no re-stamp


@pytest.mark.asyncio
async def test_half_healed_row_gets_its_side_effects_replayed(client: AsyncClient, monkeypatch):
    """A heal that died AFTER the flip (cron timeout, kill) leaves status=system_error with the
    token still on the row. Once the claim's TTL passes, the next sweep replays the side effects
    and clears the token — flipped-but-unprojected is never a resting state."""
    from app.agents import orchestrator

    cfid = await _fresh_case(client)
    async with AsyncSessionLocal() as s:
        await s.execute(
            text(
                "UPDATE case_files SET status='audit_incomplete', audit_incomplete_reason='system_error', "
                "reconcile_token=gen_random_uuid(), reconcile_claimed_at=now() - interval '1 hour', "
                "reconcile_attempts=1 WHERE case_file_id=:id"
            ),
            {"id": str(cfid)},
        )
        await s.commit()
    replayed: list[tuple] = []
    real = orchestrator._status_side_effects

    async def spy(case_file_id, status, reason, user_id, was_system_error, **kw):
        replayed.append((status, reason, kw.get("skip_review_enqueue")))
        await real(case_file_id, status, reason, user_id, was_system_error, **kw)

    monkeypatch.setattr(orchestrator, "_status_side_effects", spy)
    result = await reconcile_interrupted_runs(only_case_ids={cfid})
    assert result["replayed"] == 1 and result["audits"] == 0
    assert replayed == [("audit_incomplete", "system_error", False)]
    cf = await _row(cfid)
    assert cf.reconcile_token is None and cf.reconcile_attempts == 2
    assert cf.status == "audit_incomplete"  # a replay never moves the status

    # a claim that is still fresh belongs to a LIVE reconciler — left alone
    async with AsyncSessionLocal() as s:
        await s.execute(
            text("UPDATE case_files SET reconcile_token=gen_random_uuid(), reconcile_claimed_at=now() "
                 "WHERE case_file_id=:id"),
            {"id": str(cfid)},
        )
        await s.commit()
    assert (await reconcile_interrupted_runs(only_case_ids={cfid}))["replayed"] == 0


@pytest.mark.asyncio
async def test_side_effect_failures_are_counted_and_alert_at_max_attempts(client: AsyncClient, monkeypatch):
    """Item 7: a side-effect failure is logged AND counted — never silently dropped — and a row
    that keeps failing raises a system alert at the attempt cap."""
    from app.agents import llm_health, orchestrator
    from app.startup_reconcile import _MAX_ATTEMPTS

    async def boom(*a, **k):
        raise RuntimeError("thread bridge down")

    monkeypatch.setattr(orchestrator, "_status_side_effects", boom)
    cfid = await _fresh_case(client)
    await _strand(cfid)
    alerts_before = llm_health.system_alerts()["count"]

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result = await reconcile_interrupted_runs(only_case_ids={cfid})
        assert result["failed"] == 1 and result["audits"] == 0
        cf = await _row(cfid)
        assert cf.reconcile_attempts == attempt
        # expire the claim so the next sweep may re-pick the row
        async with AsyncSessionLocal() as s:
            await s.execute(
                text("UPDATE case_files SET reconcile_claimed_at = now() - interval '1 hour' "
                     "WHERE case_file_id=:id AND reconcile_token IS NOT NULL"),
                {"id": str(cfid)},
            )
            await s.commit()
    assert llm_health.system_alerts()["count"] == alerts_before + 1  # exactly at the cap


def test_stale_threshold_is_max_of_3x_budget_and_the_floor():
    from types import SimpleNamespace

    from app.startup_reconcile import audit_stale_seconds

    assert audit_stale_seconds(SimpleNamespace(audit_wall_clock_budget_seconds=600, audit_reconcile_stale_seconds=1800)) == 1800
    assert audit_stale_seconds(SimpleNamespace(audit_wall_clock_budget_seconds=900, audit_reconcile_stale_seconds=1800)) == 2700
    assert audit_stale_seconds(SimpleNamespace(audit_wall_clock_budget_seconds=60, audit_reconcile_stale_seconds=3600)) == 3600


@pytest.mark.asyncio
async def test_boot_sweep_takes_a_bounded_bite(monkeypatch):
    import app.main as main_module
    from app.startup_reconcile import BOOT_BUDGET_SECONDS, CRON_BUDGET_SECONDS

    seen: dict = {}

    async def spy(*a, **k):
        seen.update(k)
        return {"audits": 0, "crons": 0}

    monkeypatch.setattr(main_module, "reconcile_interrupted_runs", spy)
    async with main_module.lifespan(main_module.app):
        pass
    assert seen["budget_seconds"] == BOOT_BUDGET_SECONDS < CRON_BUDGET_SECONDS
