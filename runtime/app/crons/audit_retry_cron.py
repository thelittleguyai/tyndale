"""The audit_retry cron — work a provider refused, done later (e2e re-test 2026-09-23).

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


async def run_audit_retry_cron() -> dict:
    from app.agents.runner import real_claude_enabled

    if not real_claude_enabled():
        log.warning("audit_retry.skipped", reason="claude_not_configured")
        return {"skipped": "claude_not_configured"}
    deadline = time.monotonic() + SWEEP_BUDGET_SECONDS
    summaries = await retry_pending_summaries(deadline)
    log.info("audit_retry.done", summaries=summaries)
    return {"summaries": summaries}
