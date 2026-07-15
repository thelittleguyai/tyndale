"""Metric definitions — the ONE place every rollup's numerator, denominator, and definition live
(Internal Analytics P0, Rule 1). A ratio without a pinned definition is impossible to construct
(MetricDef.__post_init__ enforces it), and the win-rate definition is the canonical example,
stated verbatim: resolved ÷ outcomes REPORTED, never ÷ all cases.

Every metric computes from the analytics_events stream over a [start, end) day window, returning
(numerator, denominator) — denominator is None for a pure count. The nightly cron and the
substantiation export both read these; nobody redefines a metric anywhere else.
"""

from __future__ import annotations

import datetime
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.analytics_events import AnalyticsEvent

Compute = Callable[[AsyncSession, datetime.datetime, datetime.datetime], Awaitable[tuple[float, float | None]]]


@dataclass(frozen=True)
class MetricDef:
    key: str
    definition: str  # Rule 1 — the pinned, human-readable definition; never blank
    kind: str  # 'ratio' | 'count'
    compute: Compute

    def __post_init__(self) -> None:
        if not self.definition.strip():
            raise ValueError(f"metric {self.key!r} must pin a definition (Rule 1)")
        if self.kind not in ("ratio", "count"):
            raise ValueError(f"metric {self.key!r}: kind must be 'ratio' or 'count'")


async def _count(
    session: AsyncSession, name: str, start, end, *, prop: str | None = None, values: tuple[str, ...] = ()
) -> int:
    q = (
        select(func.count())
        .select_from(AnalyticsEvent)
        .where(AnalyticsEvent.event_name == name)
        .where(AnalyticsEvent.occurred_at >= start)
        .where(AnalyticsEvent.occurred_at < end)
    )
    if prop is not None:
        q = q.where(AnalyticsEvent.properties[prop].astext.in_(values))
    return (await session.execute(q)).scalar_one()


def _ratio(name_num: str, name_den: str, *, num_prop=None, num_values=(), den_prop=None, den_values=()) -> Compute:
    async def _c(session, start, end):
        num = await _count(session, name_num, start, end, prop=num_prop, values=num_values)
        den = await _count(session, name_den, start, end, prop=den_prop, values=den_values)
        return float(num), float(den)

    return _c


def _self_ratio(name: str, num_prop: str, num_values: tuple[str, ...]) -> Compute:
    """A rate whose numerator is a subset of its own denominator (e.g. not-sure ÷ all answers)."""
    async def _c(session, start, end):
        den = await _count(session, name, start, end)
        num = await _count(session, name, start, end, prop=num_prop, values=num_values)
        return float(num), float(den)

    return _c


def _pure_count(name: str) -> Compute:
    async def _c(session, start, end):
        return float(await _count(session, name, start, end)), None

    return _c


# The registry. Definitions are pinned here and NOWHERE else.
DEFINITIONS: dict[str, MetricDef] = {
    "win_rate": MetricDef(
        "win_rate",
        "Win rate = outcomes resolved (yes/partial) ÷ outcomes REPORTED — never ÷ all cases.",
        "ratio",
        _self_ratio("outcome_reported", "resolved", ("yes", "partial")),
    ),
    "outcome_report_rate": MetricDef(
        "outcome_report_rate",
        "Outcome-report rate = cases that reported an outcome ÷ audits completed (the win-rate "
        "denominator's own coverage — always shown beside win rate).",
        "ratio",
        _ratio("outcome_reported", "audit_completed"),
    ),
    "close_the_loop_rate": MetricDef(
        "close_the_loop_rate",
        "Close-the-loop rate = needs-documents requests satisfied ÷ needs-documents requests "
        "issued (distinct cases).",
        "ratio",
        _ratio("document_request_satisfied", "document_request_issued"),
    ),
    "audit_completion_rate": MetricDef(
        "audit_completion_rate",
        "Audit completion rate = audits completed ÷ audits started.",
        "ratio",
        _ratio("audit_completed", "audit_started"),
    ),
    "needs_documents_rate": MetricDef(
        "needs_documents_rate",
        "Needs-documents rate = audits ending in needs-documents ÷ audits started.",
        "ratio",
        _ratio("audit_needs_documents", "audit_started"),
    ),
    "verification_not_sure_rate": MetricDef(
        "verification_not_sure_rate",
        "'Not sure' rate = not-sure line-item answers ÷ all verification answers.",
        "ratio",
        _self_ratio("verification_answered", "answer", ("not_sure",)),
    ),
    "thumbs_down_rate": MetricDef(
        "thumbs_down_rate",
        "Thumbs-down rate = 👎 ÷ all finding feedback.",
        "ratio",
        _self_ratio("finding_feedback", "thumbs", ("down",)),
    ),
    "uploads": MetricDef("uploads", "Uploads = count of upload_started events.", "count", _pure_count("upload_started")),
    "outcomes_reported": MetricDef(
        "outcomes_reported", "Outcomes reported = count of outcome_reported events.", "count",
        _pure_count("outcome_reported"),
    ),
    "crisis_fires": MetricDef(
        "crisis_fires", "Crisis fires = count of crisis-classifier fires (count-only, no content).",
        "count", _pure_count("crisis_fire_count"),
    ),
    "refusals": MetricDef(
        "refusals", "Refusals = count of out-of-scope refusal events.", "count", _pure_count("refusal_event"),
    ),
}


async def compute_metric_row(
    session: AsyncSession, metric: MetricDef, day: datetime.date
) -> dict:
    """Compute one (metric, day) rollup. value = num/den when den>0, else None (the dashboard shows
    the raw n/d rather than a divide-by-zero). The pinned definition rides along (Rule 1)."""
    start = datetime.datetime.combine(day, datetime.time.min, tzinfo=datetime.timezone.utc)
    end = start + datetime.timedelta(days=1)
    num, den = await metric.compute(session, start, end)
    value = (num / den) if (den is not None and den > 0) else None
    return {
        "metric_key": metric.key,
        "day": day,
        "numerator": num,
        "denominator": den,
        "value": value,
        "definition": metric.definition,
    }
