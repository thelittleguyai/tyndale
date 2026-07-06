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

Residual gap (documented follow-up): an audit killed *recently* (well inside the budget) has a
recent last-transition time, so the age guard skips it until a later restart ages it out. The
proper fix is per-replica ownership tracking (a heartbeat/lease column) so "the owning process
is gone" can be proven directly rather than inferred from age; that is out of scope here.
"""

from __future__ import annotations

import datetime

import structlog
from sqlalchemy import update

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


async def reconcile_interrupted_runs(session_factory=AsyncSessionLocal) -> dict[str, int]:
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
        async with session_factory() as s:
            now = datetime.datetime.now(datetime.timezone.utc)
            audit_cutoff = now - datetime.timedelta(seconds=audit_stale_seconds)
            cron_cutoff = now - datetime.timedelta(seconds=_CRON_STALE_SECONDS)

            audit_ids = list(
                (
                    await s.execute(
                        update(CaseFile)
                        .where(
                            CaseFile.status == "audit_running",
                            CaseFile.updated_at < audit_cutoff,
                        )
                        .values(status="audit_incomplete")
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

        # Log each reconciliation individually so the interruption is auditable per row.
        for cid in audit_ids:
            log.warning(
                "reconcile.audit_interrupted",
                case_file_id=str(cid),
                reason="interrupted_by_restart",
                new_status="audit_incomplete",
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
