"""The audit_retry cron — work a provider refused, done later (e2e re-test 2026-09-23).

Item 3: §10.4 tells a system_error user "Give it another moment, or I'll email you the moment
I've got it working again" — and until now nothing ever re-ran a system_error audit, so that
email could never fire. This sweep RE-RUNS them first (the promise outranks a late summary):

  * DUE ONLY AFTER A PAUSE. The first re-run waits ``RECOVERY_FIRST_DELAY`` after the failure
    (the provider was throttling a moment ago), the second an hour after the first; only
    failures from the last ``RECOVERY_WINDOW`` are touched.
  * BOUNDED. ``RECOVERY_MAX_ATTEMPTS`` re-runs, then ``audit_retry.recovery_exhausted`` is
    logged — the alert rule (monitoring.tf) mails a person and Admin › System lists it under
    "Needs a person". ``audit_retry_force`` (manual, Admin › System › crons) retries every open
    one once the cause is fixed.
  * THE SAME RUN THE RUNTIME WOULD DO, OR NONE. A re-run needs real Claude AND — because the
    agents re-read the documents — real OCR: on a container without it the OCR tool answers
    with the stub bill (stubs/ocr.py). Missing either, the sweep skips recoveries and says why.
  * A recovered audit's terminal write fires the recovery email (orchestrator._set_status).

Item 1: an audit whose Lead Planner summary the provider still refused after the bounded
backoff finishes ``audit_complete`` with ``summary_pending`` (orchestrator._run_real_agents).
This sweep writes those summaries from the inputs the run saved:

  * CLAIM, THEN WORK. A row is claimed under ``FOR UPDATE SKIP LOCKED`` by spending an attempt
    and pushing ``summary_retry_after`` out by a lease, so two overlapping sweeps (or the
    scheduled job and an admin's manual trigger) never compose the same summary twice.
  * BOUNDED. ``SUMMARY_MAX_ATTEMPTS`` tries, backing off 15 min → 1 h → 4 h. When they are
    spent the pending flag is cleared — the page stops promising a summary that is not coming —
    and ``audit_retry.summary_exhausted`` is logged for the alert rule.
  * SAFE AGAINST A RE-RUN. The write is a compare-and-swap on "still complete and still
    pending" (orchestrator.compose_pending_summary): a fresh run in between wins.

The sweep needs Claude. Where the container carries no Claude configuration it does nothing
and says so (``skipped: claude_not_configured``) rather than burning attempts; an admin's
manual trigger runs inside the runtime, which always has it.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_, select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile

log = structlog.get_logger(__name__)

SUMMARY_MAX_ATTEMPTS = 4
# the wait after failed retry N (1-based); the first retry is due 5 min after the run
SUMMARY_BACKOFF = (timedelta(minutes=15), timedelta(hours=1), timedelta(hours=4))
# a claimed row is not picked again for this long, whatever happens to the sweep holding it
CLAIM_LEASE = timedelta(minutes=20)
# the job's container timeout is 900 s; no new work starts after this
SWEEP_BUDGET_SECONDS = 720.0

RECOVERY_MAX_ATTEMPTS = 2
RECOVERY_FIRST_DELAY = timedelta(minutes=15)
# the wait after failed re-run N (1-based)
RECOVERY_BACKOFF = (timedelta(hours=1),)
RECOVERY_WINDOW = timedelta(hours=48)
# a re-run is only STARTED with this much sweep time left (the audit's own budget + margin)
RECOVERY_HEADROOM_SECONDS = 30.0


def _backoff(attempt: int) -> timedelta:
    return SUMMARY_BACKOFF[min(attempt, len(SUMMARY_BACKOFF)) - 1]


async def _claim_summary(now: datetime) -> tuple[str, int] | None:
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CaseFile)
                .where(
                    CaseFile.summary_pending.is_(True),
                    CaseFile.status == "audit_complete",
                    CaseFile.summary_retry_attempts < SUMMARY_MAX_ATTEMPTS,
                    or_(CaseFile.summary_retry_after.is_(None), CaseFile.summary_retry_after <= now),
                )
                .order_by(CaseFile.summary_retry_after.asc().nullsfirst())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.summary_retry_attempts = (row.summary_retry_attempts or 0) + 1
        row.summary_retry_after = now + CLAIM_LEASE
        claimed = (str(row.case_file_id), row.summary_retry_attempts)
        await s.commit()
    return claimed


async def _after_failed_summary(case_file_id: str, attempt: int) -> str:
    """Back off, or — attempts spent — stop promising a summary. Returns the outcome."""
    from uuid import UUID

    from sqlalchemy import update

    exhausted = attempt >= SUMMARY_MAX_ATTEMPTS
    values = (
        {"summary_pending": False, "summary_inputs": None, "summary_retry_after": None}
        if exhausted
        else {"summary_retry_after": datetime.now(timezone.utc) + _backoff(attempt)}
    )
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile)
            .where(CaseFile.case_file_id == UUID(case_file_id), CaseFile.summary_pending.is_(True))
            .values(**values)
        )
        await s.commit()
    if exhausted:
        log.error("audit_retry.summary_exhausted", case_file_id=case_file_id, attempts=attempt)
        return "exhausted"
    log.warning("audit_retry.summary_backoff", case_file_id=case_file_id, attempt=attempt)
    return "backoff"


async def retry_pending_summaries(deadline: float, *, compose=None) -> dict[str, int]:
    """Work the due owed summaries until none is due or the sweep budget is spent."""
    if compose is None:
        from app.agents.orchestrator import compose_pending_summary as compose
    tally = {"written": 0, "backoff": 0, "exhausted": 0, "superseded": 0}
    while time.monotonic() < deadline:
        claimed = await _claim_summary(datetime.now(timezone.utc))
        if claimed is None:
            break
        case_file_id, attempt = claimed
        try:
            written = await compose(case_file_id)
        except Exception:  # noqa: BLE001 — one bad row must not stop the sweep
            log.error("audit_retry.summary_crashed", case_file_id=case_file_id, exc_info=True)
            written = None
        if written is not None:
            tally["written"] += 1
            continue
        still_owed = await _still_owed(case_file_id)
        if not still_owed:
            tally["superseded"] += 1
            continue
        tally[await _after_failed_summary(case_file_id, attempt)] += 1
    return tally


async def _still_owed(case_file_id: str) -> bool:
    from uuid import UUID

    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CaseFile.summary_pending, CaseFile.status).where(
                    CaseFile.case_file_id == UUID(case_file_id)
                )
            )
        ).first()
    return bool(row and row[0] and row[1] == "audit_complete")


def recovery_blocker() -> str | None:
    """Why a recovery re-run may NOT run in this container, or None when it may."""
    from app.agents.runner import real_claude_enabled
    from app.config import get_settings

    s = get_settings()
    if not s.enable_audit_auto_recovery:
        return "auto_recovery_disabled"
    if not real_claude_enabled():
        return "claude_not_configured"
    if not (s.use_real_ocr and s.azure_doc_intelligence_endpoint and s.azure_doc_intelligence_key):
        return "ocr_not_configured"
    return None


def _recovery_due(now: datetime, *, force: bool):
    from sqlalchemy import and_

    due = [
        CaseFile.status == "audit_incomplete",
        CaseFile.audit_incomplete_reason == "system_error",
        CaseFile.reconcile_token.is_(None),  # the stranded-audit healer is mid-flight on it
        CaseFile.soft_deleted_at.is_(None),
    ]
    if force:
        # an admin's retry-everything-open: past the cap and the window (a week back), but still
        # never two sweeps on one row — the lease below still applies
        due.append(CaseFile.updated_at >= now - timedelta(days=7))
        due.append(or_(CaseFile.recovery_retry_after.is_(None), CaseFile.recovery_retry_after <= now))
        return due
    due += [
        CaseFile.recovery_attempts < RECOVERY_MAX_ATTEMPTS,
        CaseFile.updated_at >= now - RECOVERY_WINDOW,
        or_(
            and_(CaseFile.recovery_retry_after.is_(None), CaseFile.updated_at <= now - RECOVERY_FIRST_DELAY),
            CaseFile.recovery_retry_after <= now,
        ),
    ]
    return due


async def _claim_recovery(now: datetime, *, force: bool = False) -> tuple[str, int] | None:
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CaseFile)
                .where(*_recovery_due(now, force=force))
                .order_by(CaseFile.updated_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.recovery_attempts = (row.recovery_attempts or 0) + 1
        # the lease AND the backoff: if this re-run fails, the next is not due before this
        backoff = RECOVERY_BACKOFF[min(row.recovery_attempts, len(RECOVERY_BACKOFF)) - 1]
        row.recovery_retry_after = now + max(backoff, CLAIM_LEASE)
        claimed = (str(row.case_file_id), row.recovery_attempts)
        await s.commit()
    return claimed


async def recover_system_errors(deadline: float, *, force: bool = False, rerun=None) -> dict[str, int]:
    """Re-run due system_error audits while the sweep can still hold a whole audit."""
    from app.config import get_settings

    if rerun is None:
        from app.agents.orchestrator import finalize_audit

        async def rerun(case_file_id: str):
            return await finalize_audit(case_file_id, recovery=True)

    tally = {"recovered": 0, "needs_documents": 0, "failed_again": 0, "exhausted": 0, "superseded": 0}
    needed = get_settings().audit_wall_clock_budget_seconds + RECOVERY_HEADROOM_SECONDS
    while deadline - time.monotonic() >= needed:
        claimed = await _claim_recovery(datetime.now(timezone.utc), force=force)
        if claimed is None:
            break
        case_file_id, attempt = claimed
        log.warning("audit_retry.recovery_started", case_file_id=case_file_id, attempt=attempt, forced=force)
        try:
            result = await rerun(case_file_id)
        except Exception:  # noqa: BLE001 — finalize already wrote system_error + alerted
            result = None
            log.error("audit_retry.recovery_crashed", case_file_id=case_file_id, exc_info=True)
        outcome = await _recovery_outcome(case_file_id, result)
        if outcome == "failed_again" and attempt >= RECOVERY_MAX_ATTEMPTS:
            outcome = "exhausted"
            log.error("audit_retry.recovery_exhausted", case_file_id=case_file_id, attempts=attempt)
        tally[outcome] += 1
        log.warning("audit_retry.recovery_done", case_file_id=case_file_id, attempt=attempt, outcome=outcome)
    return tally


async def _recovery_outcome(case_file_id: str, _result) -> str:
    from uuid import UUID

    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CaseFile.status, CaseFile.audit_incomplete_reason).where(
                    CaseFile.case_file_id == UUID(case_file_id)
                )
            )
        ).first()
    if row is None:
        return "superseded"
    status, reason = row
    if status == "audit_complete":
        return "recovered"
    if status == "audit_incomplete" and reason == "needs_documents":
        return "needs_documents"
    if status == "audit_incomplete" and reason == "system_error":
        return "failed_again"
    return "superseded"


async def _sweep(*, force: bool) -> dict:
    from app.agents.runner import real_claude_enabled

    if not real_claude_enabled():
        log.warning("audit_retry.skipped", reason="claude_not_configured")
        return {"skipped": "claude_not_configured"}
    deadline = time.monotonic() + SWEEP_BUDGET_SECONDS
    blocker = recovery_blocker()
    if blocker is None:
        recoveries: dict | str = await recover_system_errors(deadline, force=force)
    else:
        log.warning("audit_retry.recovery_skipped", reason=blocker)
        recoveries = f"skipped: {blocker}"
    summaries = await retry_pending_summaries(deadline)
    log.info("audit_retry.done", recoveries=recoveries, summaries=summaries)
    return {"recoveries": recoveries, "summaries": summaries}


async def run_audit_retry_cron() -> dict:
    return await _sweep(force=False)


async def run_audit_retry_force_cron() -> dict:
    """Manual only (Admin › System › crons): once the cause is fixed, re-run EVERY open
    system_error audit from the last week once — past the attempt cap."""
    return await _sweep(force=True)
