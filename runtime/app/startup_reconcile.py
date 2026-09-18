"""Startup reconciliation sweep (2026-07-06).

A SIGKILL / deploy roll / OOM kill can terminate a replica mid-audit or mid-cron, stranding
rows in a non-terminal 'running' state that nothing will ever finish — the frontend polls an
audit forever, and the admin cron history shows a run that never ended. On startup we sweep
for those and mark them terminal:

  - case_files stuck in 'audit_running' whose last transition is older than the audit
    wall-clock budget + a safety buffer -> 'audit_incomplete'. Any partials already computed
    are kept (we only flip status). The age guard is the safety mechanism: an audit that could
    still legitimately be in flight on a *concurrent* replica is younger than the budget and is
    never touched — we only reconcile ones that provably cannot still be running.
  - cron_run_log rows stuck in 'running' past a generous ceiling -> 'interrupted'.

This never raises: a reconciliation failure must not stop the app from booting.

Since 2026-09-18 the same sweep also runs as the `stuck_audits` cron (every 15 min), so a case
stranded between deploys heals within ~budget + buffer + 15 min instead of waiting for the
next boot; and a reconciled audit goes through the orchestrator's status chokepoint
(_set_status) as audit_incomplete / system_error — the honest apology copy (never the
needs_documents default), the chat-thread projection, the lifecycle event, the §10.4 recovery
promise, the review-queue enqueue with its system_error trigger, and the admin alert counter.
Residual gap: age-based detection still can't prove "the owning process is gone" for a kill
inside the budget window; per-replica ownership (a heartbeat/lease column) remains the proper
fix and is out of scope here.
"""

from __future__ import annotations

import asyncio
import datetime

import structlog
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError, InterfaceError

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.cron_run_log import CronRunLog

log = structlog.get_logger(__name__)

# A cron can legitimately run long (bulk MRF ingest). Only reconcile ones older than this
# ceiling — well beyond any real cron duration — so a genuinely-running job is never clobbered.
_CRON_STALE_SECONDS = 6 * 60 * 60  # 6h
# Buffer added to the audit budget before a stuck audit_running case is considered dead.
_AUDIT_STALE_BUFFER_SECONDS = 300  # 5 min beyond the wall-clock budget


_CLAIM_ATTEMPTS = 3
_CLAIM_RETRY_DELAY_S = 2.0


async def _claim_with_retry(session_factory, audit_stale_seconds: int, *, sleep=asyncio.sleep):
    """The claim UPDATEs, retried on a broken connection. The dev boot of 2026-09-18 18:13
    lost its first connection mid-statement (asyncpg ConnectionDoesNotExistError after an SSL
    'bad record mac') and the whole sweep was skipped until the next boot; pool_pre_ping only
    guards checkout, not a TLS stream that dies under a statement. Each attempt is a fresh
    session, so a poisoned pooled connection is discarded rather than reused."""
    last: Exception | None = None
    for attempt in range(1, _CLAIM_ATTEMPTS + 1):
        try:
            async with session_factory() as s:
                now = datetime.datetime.now(datetime.timezone.utc)
                audit_cutoff = now - datetime.timedelta(seconds=audit_stale_seconds)
                cron_cutoff = now - datetime.timedelta(seconds=_CRON_STALE_SECONDS)

                # Atomic claim: a concurrent sweep (second replica booting, the cron) can't reconcile
                # the same row twice. The reason is written HERE so a reader between the claim and
                # the chokepoint pass below never sees the needs_documents default.
                audit_ids = list(
                    (
                        await s.execute(
                            update(CaseFile)
                            .where(
                                CaseFile.status == "audit_running",
                                CaseFile.updated_at < audit_cutoff,
                            )
                            .values(
                                status="audit_incomplete", audit_incomplete_reason="system_error"
                            )
                            .returning(CaseFile.case_file_id)
                        )
                    ).scalars()
                )
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
            return audit_ids, cron_ids, now
        except (OSError, DBAPIError, InterfaceError) as exc:
            last = exc
            log.warning(
                "reconcile.claim_retry",
                attempt=attempt,
                attempts=_CLAIM_ATTEMPTS,
                error_class=type(exc).__name__,
            )
            if attempt < _CLAIM_ATTEMPTS:
                await sleep(_CLAIM_RETRY_DELAY_S)
    assert last is not None
    raise last


async def reconcile_interrupted_runs(
    session_factory=AsyncSessionLocal, *, sleep=asyncio.sleep
) -> dict[str, int]:
    """Flip stranded non-terminal 'running' audits and crons to a terminal interrupted state.

    Returns {"audits": n, "crons": m} counts. Best-effort: any error is logged and swallowed so
    that startup never fails on reconciliation.
    """
    settings = get_settings()
    # case_files.updated_at bumps on every write (onupdate=now()); for a case stuck in
    # 'audit_running' it equals the moment the audit went running. budget + buffer guarantees an
    # in-flight audit (necessarily younger than the budget) is never reconciled out from under a
    # concurrent replica.
    audit_stale_seconds = settings.audit_wall_clock_budget_seconds + _AUDIT_STALE_BUFFER_SECONDS
    try:
        audit_ids, cron_ids, now = await _claim_with_retry(
            session_factory, audit_stale_seconds, sleep=sleep
        )

        # Each reconciled audit then goes through the status chokepoint for its side effects
        # (thread projection, lifecycle event, review-queue enqueue, emails policy) and counts
        # as a system_error alert — the ONLY terminal that tells the user "our team has been
        # notified". Per row, so one failure can't strand the rest.
        for cid in audit_ids:
            log.warning(
                "reconcile.audit_interrupted",
                case_file_id=str(cid),
                reason="interrupted_by_restart",
                new_status="audit_incomplete",
                incomplete_reason="system_error",
            )
            try:
                from app.agents.llm_health import record_system_alert
                from app.agents.orchestrator import _set_status

                await _set_status(str(cid), "audit_incomplete", incomplete_reason="system_error")
                record_system_alert()
            except Exception:  # noqa: BLE001 — the claim already made the status honest
                log.error(
                    "reconcile.audit_side_effects_failed", case_file_id=str(cid), exc_info=True
                )
        for rid in cron_ids:
            log.warning(
                "reconcile.cron_interrupted",
                run_id=str(rid),
                reason="interrupted_by_restart",
                new_status="interrupted",
            )
        result = {"audits": len(audit_ids), "crons": len(cron_ids)}
        if result["audits"] or result["crons"]:
            log.info("reconcile.startup_sweep_complete", **result)
        return result
    except Exception:  # noqa: BLE001 — startup must never fail on a reconciliation error
        log.error("reconcile.startup_sweep_failed", exc_info=True)
        return {"audits": 0, "crons": 0}
