"""Stranded-run reconciliation — at boot and as the `stuck_audits` cron (2026-07-06; rebuilt
2026-09-18 after deep review C2).

A SIGKILL / deploy roll / OOM kill can terminate a replica mid-audit or mid-cron, stranding
rows in a non-terminal 'running' state that nothing will ever finish. This sweep heals them —
and is built so it can never harm a run that is alive or has finished:

  * DEAD means the HEARTBEAT is stale. The orchestrator bumps case_files.audit_heartbeat_at when
    an audit goes running and at every phase boundary; a case is a candidate only when that beat
    (updated_at for pre-heartbeat rows) is older than max(3 x audit budget,
    AUDIT_RECONCILE_STALE_SECONDS). The old rule — budget + 5 min against updated_at, which
    nothing refreshed mid-run — could "heal" a slow live audit under load.
  * CLAIM, THEN COMPARE-AND-SWAP. The claim stamps a per-sweep token on a row that is STILL
    audit_running; it does not flip the status. The terminal write goes through the
    orchestrator's chokepoint as `_set_status(expected_status="audit_running",
    expected_reconcile_token=token)`: if a live replica finished the audit in between, nothing
    is written, no side effect fires, and we log reconcile.lost_race. (The old follow-up was
    unconditional and stomped audit_complete back to system_error.)
  * ONE ROW AT A TIME, under a sweep budget. Each row is claimed, flipped and given its side
    effects (thread projection, lifecycle event, review enqueue, alert) before the next is
    touched, so a timeout leaves the remainder unclaimed and re-pickable — never flipped-but-
    unprojected. A heal that dies AFTER the flip keeps its token; once the claim's TTL passes,
    the next sweep re-claims the row and REPLAYS the side effects (all idempotent).
  * EVERY ATTEMPT IS COUNTED (reconcile_attempts) and a row that keeps failing raises a system
    alert at _MAX_ATTEMPTS — a side-effect failure is never silently dropped.

cron_run_log rows stuck 'running' past a generous ceiling -> 'interrupted' (one atomic UPDATE;
no side effects, so no per-row dance). The sweep never raises: boot must not fail on it.
"""

from __future__ import annotations

import asyncio
import datetime
import time
import uuid

import structlog
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import DBAPIError, InterfaceError

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CaseReview
from app.db.models.cron_run_log import CronRunLog

log = structlog.get_logger(__name__)

# A cron can legitimately run long (bulk MRF ingest). Only reconcile ones older than this
# ceiling — well beyond any real cron duration — so a genuinely-running job is never clobbered.
_CRON_STALE_SECONDS = 6 * 60 * 60  # 6h
# A claim older than this belongs to a reconciler that died (the cron's own timeout is 300 s).
_CLAIM_TTL_SECONDS = 600
# Attempts before a row that keeps failing raises a system alert.
_MAX_ATTEMPTS = 3
# Rows considered per sweep — a backlog is worked down across sweeps, oldest first.
_BATCH_LIMIT = 100
# Sweep budgets: boot blocks serving, so it takes a bite and leaves the rest to the cron; the
# cron's container timeout is 300 s, so it stops starting new rows well before that.
BOOT_BUDGET_SECONDS = 20.0
CRON_BUDGET_SECONDS = 240.0

_LIST_ATTEMPTS = 3
_LIST_RETRY_DELAY_S = 2.0


def audit_stale_seconds(settings=None) -> int:
    """How old a running audit's heartbeat must be before it is considered dead."""
    s = settings or get_settings()
    return max(3 * int(s.audit_wall_clock_budget_seconds), int(s.audit_reconcile_stale_seconds))


def _last_beat():
    return func.coalesce(CaseFile.audit_heartbeat_at, CaseFile.updated_at)


def _claim_free(claim_cutoff):
    return or_(CaseFile.reconcile_token.is_(None), CaseFile.reconcile_claimed_at < claim_cutoff)


async def _list_work_with_retry(session_factory, stale_seconds: int, only, *, sleep=asyncio.sleep):
    """Find the work (no audit writes) and flip stale cron rows, retried on a broken connection.
    The dev boot of 2026-09-18 18:13 lost its first connection mid-statement (asyncpg
    ConnectionDoesNotExistError after an SSL 'bad record mac'); pool_pre_ping only guards
    checkout. Each attempt is a fresh session, so a poisoned pooled connection is discarded."""
    last: Exception | None = None
    for attempt in range(1, _LIST_ATTEMPTS + 1):
        try:
            async with session_factory() as s:
                now = datetime.datetime.now(datetime.timezone.utc)
                cutoff = now - datetime.timedelta(seconds=stale_seconds)
                claim_cutoff = now - datetime.timedelta(seconds=_CLAIM_TTL_SECONDS)
                cron_cutoff = now - datetime.timedelta(seconds=_CRON_STALE_SECONDS)
                dead_q = (
                    select(CaseFile.case_file_id)
                    .where(
                        CaseFile.status == "audit_running",
                        _last_beat() < cutoff,
                        _claim_free(claim_cutoff),
                    )
                    .order_by(_last_beat().asc())
                    .limit(_BATCH_LIMIT)
                )
                # Flipped by a reconciler that died before finishing the side effects.
                half_q = (
                    select(CaseFile.case_file_id)
                    .where(
                        CaseFile.status == "audit_incomplete",
                        CaseFile.audit_incomplete_reason == "system_error",
                        CaseFile.reconcile_token.is_not(None),
                        CaseFile.reconcile_claimed_at < claim_cutoff,
                    )
                    .order_by(CaseFile.reconcile_claimed_at.asc())
                    .limit(_BATCH_LIMIT)
                )
                if only is not None:
                    dead_q = dead_q.where(CaseFile.case_file_id.in_(only))
                    half_q = half_q.where(CaseFile.case_file_id.in_(only))
                dead = list((await s.execute(dead_q)).scalars())
                half = list((await s.execute(half_q)).scalars())
                cron_ids = list(
                    (
                        await s.execute(
                            update(CronRunLog)
                            .where(
                                CronRunLog.status == "running",
                                CronRunLog.started_at < cron_cutoff,
                            )
                            .values(
                                status="interrupted",
                                finished_at=now,
                                error_message=(
                                    "reconciled on startup: owning process died mid-run "
                                    "(interrupted_by_restart)"
                                ),
                            )
                            .returning(CronRunLog.run_id)
                        )
                    ).scalars()
                )
                await s.commit()
            return dead, half, cron_ids
        except (OSError, DBAPIError, InterfaceError) as exc:
            last = exc
            log.warning(
                "reconcile.claim_retry",
                attempt=attempt,
                attempts=_LIST_ATTEMPTS,
                error_class=type(exc).__name__,
            )
            if attempt < _LIST_ATTEMPTS:
                await sleep(_LIST_RETRY_DELAY_S)
    assert last is not None
    raise last


async def _claim(session_factory, cid, token: uuid.UUID, stale_seconds: int, *, half_healed: bool):
    """Stamp our token on the row iff it is STILL the work we listed (re-checked in the UPDATE's
    own WHERE — the list is only a hint). Returns (attempts, claimed_at_before) or None.
    updated_at is pinned so a claim never makes a pre-heartbeat row look fresh."""
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(seconds=stale_seconds)
    claim_cutoff = now - datetime.timedelta(seconds=_CLAIM_TTL_SECONDS)
    if half_healed:
        cond = and_(
            CaseFile.status == "audit_incomplete",
            CaseFile.audit_incomplete_reason == "system_error",
            CaseFile.reconcile_token.is_not(None),
            CaseFile.reconcile_claimed_at < claim_cutoff,
        )
    else:
        cond = and_(
            CaseFile.status == "audit_running", _last_beat() < cutoff, _claim_free(claim_cutoff)
        )
    async with session_factory() as s:
        prior = (
            await s.execute(
                select(CaseFile.reconcile_claimed_at).where(CaseFile.case_file_id == cid)
            )
        ).scalar_one_or_none()
        attempts = (
            await s.execute(
                update(CaseFile)
                .where(CaseFile.case_file_id == cid, cond)
                .values(
                    reconcile_token=token,
                    reconcile_claimed_at=now,
                    reconcile_attempts=CaseFile.reconcile_attempts + 1,
                    updated_at=CaseFile.updated_at,
                )
                .returning(CaseFile.reconcile_attempts)
            )
        ).scalar_one_or_none()
        await s.commit()
    return None if attempts is None else (int(attempts), prior)


async def _release(session_factory, cid, token: uuid.UUID) -> None:
    """Drop our claim (only if it is still ours)."""
    async with session_factory() as s:
        await s.execute(
            update(CaseFile)
            .where(CaseFile.case_file_id == cid, CaseFile.reconcile_token == token)
            .values(
                reconcile_token=None, reconcile_claimed_at=None, updated_at=CaseFile.updated_at
            )
        )
        await s.commit()


def _attempts_exhausted(cid, attempts: int) -> None:
    from app.agents.llm_health import record_system_alert

    record_system_alert()
    log.error("reconcile.attempts_exhausted", case_file_id=str(cid), attempts=attempts)


async def _heal_dead(session_factory, cid, token, stale_seconds, after_claim) -> str:
    from app.agents.llm_health import record_system_alert
    from app.agents.orchestrator import _set_status

    claimed = await _claim(session_factory, cid, token, stale_seconds, half_healed=False)
    if claimed is None:
        return "skipped"  # it moved on, or another sweep holds it
    attempts, _prior = claimed
    if after_claim is not None:  # test seam: "another replica finishes the audit right here"
        await after_claim(cid)
    try:
        applied = await _set_status(
            str(cid),
            "audit_incomplete",
            incomplete_reason="system_error",
            expected_status="audit_running",
            expected_reconcile_token=token,
        )
    except Exception:  # noqa: BLE001 — counted (the claim already incremented), never dropped
        log.error(
            "reconcile.audit_side_effects_failed",
            case_file_id=str(cid), attempts=attempts, exc_info=True,
        )
        if attempts >= _MAX_ATTEMPTS:
            _attempts_exhausted(cid, attempts)
        # The token stays: if the flip landed, the half-healed pass replays the side effects
        # after the claim TTL; if it did not, the row is still audit_running and is re-claimed.
        return "failed"
    if not applied:
        log.warning("reconcile.lost_race", case_file_id=str(cid))
        await _release(session_factory, cid, token)
        return "lost_race"
    await _release(session_factory, cid, token)
    record_system_alert()
    log.warning(
        "reconcile.audit_interrupted",
        case_file_id=str(cid),
        reason="interrupted_by_restart",
        new_status="audit_incomplete",
        incomplete_reason="system_error",
        attempts=attempts,
    )
    return "healed"


async def _replay_half_healed(session_factory, cid, token, stale_seconds) -> str:
    """The previous heal flipped the row and died before finishing. Re-claim it and replay the
    chokepoint's side effects — skipping the review enqueue when that run is already queued."""
    from app.agents.orchestrator import _status_side_effects

    claimed = await _claim(session_factory, cid, token, stale_seconds, half_healed=True)
    if claimed is None:
        return "skipped"
    attempts, flipped_at = claimed
    try:
        async with session_factory() as s:
            case = await s.get(CaseFile, cid)
            user_id = case.user_id if case else None
            already_queued = False
            if flipped_at is not None:
                already_queued = (
                    await s.execute(
                        select(func.count())
                        .select_from(CaseReview)
                        .where(
                            CaseReview.case_file_id == cid,
                            CaseReview.system_error.is_(True),
                            CaseReview.enqueued_at >= flipped_at,
                        )
                    )
                ).scalar_one() > 0
        await _status_side_effects(
            str(cid), "audit_incomplete", "system_error", user_id, False,
            skip_review_enqueue=already_queued,
        )
    except Exception:  # noqa: BLE001
        log.error(
            "reconcile.audit_side_effects_failed",
            case_file_id=str(cid), attempts=attempts, replay=True, exc_info=True,
        )
        if attempts >= _MAX_ATTEMPTS:
            _attempts_exhausted(cid, attempts)
            await _release(session_factory, cid, token)  # stop replaying; the alert stands
        return "failed"
    await _release(session_factory, cid, token)
    log.warning("reconcile.side_effects_replayed", case_file_id=str(cid), attempts=attempts)
    return "replayed"


async def reconcile_interrupted_runs(
    session_factory=AsyncSessionLocal,
    *,
    sleep=asyncio.sleep,
    budget_seconds: float = CRON_BUDGET_SECONDS,
    clock=time.monotonic,
    only_case_ids=None,
    _after_claim=None,
) -> dict[str, int]:
    """Heal stranded audits and crons. Returns counts — ``audits`` (healed) and ``crons`` plus
    ``lost_race`` / ``replayed`` / ``failed`` / ``deferred``. Best-effort: any error is logged
    and swallowed so that startup never fails on reconciliation. ``only_case_ids`` scopes the
    audit pass (an operator healing one case; the tests)."""
    out = {"audits": 0, "crons": 0, "lost_race": 0, "replayed": 0, "failed": 0, "deferred": 0}
    try:
        stale = audit_stale_seconds()
        only = None if only_case_ids is None else list(only_case_ids)
        dead, half, cron_ids = await _list_work_with_retry(session_factory, stale, only, sleep=sleep)
        for rid in cron_ids:
            log.warning(
                "reconcile.cron_interrupted",
                run_id=str(rid), reason="interrupted_by_restart", new_status="interrupted",
            )
        out["crons"] = len(cron_ids)

        token = uuid.uuid4()
        started = clock()
        work = [(cid, False) for cid in dead] + [(cid, True) for cid in half]
        for i, (cid, is_half) in enumerate(work):
            if clock() - started > budget_seconds:
                out["deferred"] = len(work) - i
                log.warning("reconcile.sweep_budget_exhausted", deferred=out["deferred"])
                break
            try:
                if is_half:
                    outcome = await _replay_half_healed(session_factory, cid, token, stale)
                else:
                    outcome = await _heal_dead(session_factory, cid, token, stale, _after_claim)
            except Exception:  # noqa: BLE001 — one bad row must not strand the rest
                log.error("reconcile.row_failed", case_file_id=str(cid), exc_info=True)
                outcome = "failed"
            if outcome == "healed":
                out["audits"] += 1
            elif outcome in out:
                out[outcome] += 1
        if any(out.values()):
            log.info("reconcile.startup_sweep_complete", **out)
        return out
    except Exception:  # noqa: BLE001 — startup must never fail on a reconciliation error
        log.error("reconcile.startup_sweep_failed", exc_info=True)
        return out
