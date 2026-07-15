"""Daily rollup + historical backfill (Internal Analytics P0, §2).

`rollup_day` computes every metric for one day from the live analytics_events stream and upserts
the analytics_daily rows (idempotent per metric+day). `backfill_day_from_sources` derives the
flagship metrics from the pre-instrumentation SOURCE tables (feedback_events, case_files) so the
dashboard isn't empty on day one — those rows are flagged ``backfilled=True`` so live and historical
ranges are never confused. Both write the pinned definition (Rule 1) with every row.
"""

from __future__ import annotations

import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.definitions import DEFINITIONS, compute_metric_row
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_daily import AnalyticsDaily
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent

log = structlog.get_logger(__name__)


async def _upsert(session: AsyncSession, row: dict, *, backfilled: bool) -> None:
    stmt = (
        pg_insert(AnalyticsDaily.__table__)
        .values(**row, backfilled=backfilled)
        .on_conflict_do_update(
            index_elements=["metric_key", "day"],
            set_={
                "numerator": row["numerator"],
                "denominator": row["denominator"],
                "value": row["value"],
                "definition": row["definition"],
                "backfilled": backfilled,
                "computed_at": func.now(),
            },
        )
    )
    await session.execute(stmt)


async def rollup_day(session: AsyncSession, day: datetime.date) -> int:
    """Compute + upsert every metric for `day` from the live event stream. Returns the row count."""
    for metric in DEFINITIONS.values():
        row = await compute_metric_row(session, metric, day)
        await _upsert(session, row, backfilled=False)
    await session.commit()
    return len(DEFINITIONS)


async def run_rollup(days_back: int = 2) -> dict:
    """Nightly cron entry: roll up the last `days_back` days (a small look-back catches late events
    and idempotently re-computes yesterday)."""
    today = datetime.datetime.now(datetime.timezone.utc).date()
    total = 0
    async with AsyncSessionLocal() as s:
        for delta in range(1, days_back + 1):
            total += await rollup_day(s, today - datetime.timedelta(days=delta))
    log.info("analytics.rollup.done", days=days_back, rows=total)
    return {"days": days_back, "rows_written": total}


# --- historical backfill from source tables ---------------------------------
async def _count_where(session, model, start, end, *conds) -> int:
    q = (
        select(func.count()).select_from(model)
        .where(model.created_at >= start).where(model.created_at < end)
    )
    for c in conds:
        q = q.where(c)
    return (await session.execute(q)).scalar_one()


async def backfill_day_from_sources(session: AsyncSession, day: datetime.date) -> int:
    """Derive the flagship metrics for `day` from source tables (cases/feedback), attributed by row
    creation date. Approximate by nature (status changes aren't dated) — hence backfilled=True."""
    start = datetime.datetime.combine(day, datetime.time.min, tzinfo=datetime.timezone.utc)
    end = start + datetime.timedelta(days=1)

    uploads = await _count_where(session, CaseFile, start, end)
    completed = await _count_where(session, CaseFile, start, end, CaseFile.status == "audit_complete")
    needs_docs = await _count_where(
        session, CaseFile, start, end,
        CaseFile.status == "audit_incomplete", CaseFile.audit_incomplete_reason == "needs_documents",
    )
    outcomes = await _count_where(session, FeedbackEvent, start, end,
                                  FeedbackEvent.feedback_type == "outcome_report")
    resolved = await _count_where(
        session, FeedbackEvent, start, end,
        FeedbackEvent.feedback_type == "outcome_report",
        FeedbackEvent.payload["outcome"]["resolved"].astext.in_(("yes", "partial")),
    )

    def _row(key, num, den):
        value = (num / den) if (den is not None and den > 0) else None
        return {"metric_key": key, "day": day, "numerator": float(num),
                "denominator": None if den is None else float(den), "value": value,
                "definition": DEFINITIONS[key].definition}

    rows = [
        _row("uploads", uploads, None),
        _row("outcomes_reported", outcomes, None),
        _row("win_rate", resolved, outcomes),
        _row("audit_completion_rate", completed, uploads),
        _row("needs_documents_rate", needs_docs, uploads),
    ]
    for r in rows:
        await _upsert(session, r, backfilled=True)
    await session.commit()
    return len(rows)


async def run_backfill(start_day: datetime.date, end_day: datetime.date) -> dict:
    """Backfill [start_day, end_day] inclusive from source tables. Live rollup overwrites any day
    once real events exist (backfilled flips to False)."""
    total = 0
    async with AsyncSessionLocal() as s:
        day = start_day
        while day <= end_day:
            total += await backfill_day_from_sources(s, day)
            day += datetime.timedelta(days=1)
    log.info("analytics.backfill.done", start=str(start_day), end=str(end_day), rows=total)
    return {"start": str(start_day), "end": str(end_day), "rows_written": total}
