"""GET /v1/admin/analytics — the internal analytics dashboard data (Internal Analytics P0, §1-§6).

Serves the aggregated rollups grouped into the spec's panels. EVERY ratio carries its raw
numerator, denominator, and pinned definition (Rule 1) — the client renders n/d beside the
percentage and can never show a rate without them. Also serves the drop counters and a status
board (feature flags + registered crons + billing events awaiting emission). Admin-gated (a
non-admin gets 404). Read-only.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.definitions import DEFINITIONS
from app.agents.context_loader import DOCTRINE_VIOLATIONS
from app.agents.thread_bridge import get_bridge_conflicts
from app.analytics.emit import get_drop_counts
from app.analytics.events import REGISTRY
from app.auth import CurrentUser
from app.config import get_settings
from app.crons.registry import list_crons
from app.db.models.analytics_daily import AnalyticsDaily
from app.db.session import get_session
from app.routes.admin._deps import admin_user

router = APIRouter(tags=["v1-admin"])


class MetricOut(BaseModel):
    key: str
    definition: str  # Rule 1 — always present
    kind: str  # 'ratio' | 'count'
    numerator: float
    denominator: float | None
    value: float | None
    backfilled: bool = False


class AnalyticsPanel(BaseModel):
    key: str
    title: str
    metrics: list[MetricOut]


class StatusBoard(BaseModel):
    flags: dict[str, bool]
    crons: list[str]
    drop_counts: dict[str, int]
    not_yet_live_events: list[str]  # billing-dependent — registered, emitting nothing yet
    # Doctrine violations since boot, keyed `b_without_citation:<key>` / `missing_variable:<key>`
    # (deep review nit 1). The renderer already degrades safely on both, so nothing breaks — which
    # is exactly why they need a place to be SEEN. A [B] string that keeps rendering its
    # degradation variant is a citation that never got wired, and it looks like silence.
    doctrine_violations: dict[str, int]
    # Thread-marker collisions caught by the 0039 unique index. Harmless individually (the entry
    # exists exactly once either way); a rising count means concurrent bridge writers.
    bridge_conflicts: dict[str, int]


class AnalyticsResponse(BaseModel):
    window_days: int
    panels: list[AnalyticsPanel]
    status: StatusBoard


# Which metrics live in which panel, in render order (Rule 4: counts before ratios within a panel).
_PANELS: list[tuple[str, str, list[str]]] = [
    ("funnel", "Funnel", ["uploads", "audit_completion_rate", "needs_documents_rate"]),
    ("engagement", "Engagement", ["close_the_loop_rate", "verification_not_sure_rate"]),
    ("outcomes", "Outcomes", ["outcomes_reported", "win_rate", "outcome_report_rate"]),
    ("accuracy", "Accuracy & trust", ["thumbs_down_rate"]),
    ("compliance", "Compliance counters", ["crisis_fires", "refusals"]),
]

_FLAG_KEYS = (
    "enable_chat_first_audit", "enable_record_view", "enable_billing",
    "enable_first_case_unlock", "enable_nudge_emails", "use_real_ocr", "use_foundry",
)


@router.get("/admin/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(default=30, ge=1, le=365),
    _admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsResponse:
    cutoff = datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=days)
    rows = (
        await session.execute(
            select(
                AnalyticsDaily.metric_key,
                func.sum(AnalyticsDaily.numerator),
                func.sum(AnalyticsDaily.denominator),
                func.bool_or(AnalyticsDaily.backfilled),
            )
            .where(AnalyticsDaily.day >= cutoff)
            .group_by(AnalyticsDaily.metric_key)
        )
    ).all()
    summed = {r[0]: (float(r[1] or 0.0), r[2], bool(r[3])) for r in rows}

    def _metric(key: str) -> MetricOut:
        d = DEFINITIONS[key]
        num, den, backfilled = summed.get(key, (0.0, None, False))
        den_f = None if den is None else float(den)
        # Rule 1: a ratio ALWAYS names its denominator — 0 when there's no data yet, never None
        # (a count legitimately has no denominator). This is what the fresh-DB case exercises.
        if d.kind == "ratio" and den_f is None:
            den_f = 0.0
        value = (num / den_f) if (den_f and den_f > 0) else None
        return MetricOut(
            key=key, definition=d.definition, kind=d.kind,
            numerator=num, denominator=den_f, value=value, backfilled=backfilled,
        )

    panels = [
        AnalyticsPanel(key=k, title=t, metrics=[_metric(m) for m in keys if m in DEFINITIONS])
        for k, t, keys in _PANELS
    ]
    settings = get_settings()
    status = StatusBoard(
        flags={f: bool(getattr(settings, f, False)) for f in _FLAG_KEYS},
        crons=list_crons(),
        drop_counts=get_drop_counts(),
        not_yet_live_events=sorted(n for n, s in REGISTRY.items() if s.not_yet_live),
        doctrine_violations=dict(DOCTRINE_VIOLATIONS),
        bridge_conflicts=get_bridge_conflicts(),
    )
    return AnalyticsResponse(window_days=days, panels=panels, status=status)
