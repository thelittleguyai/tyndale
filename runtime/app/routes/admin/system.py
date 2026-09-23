"""Admin system health (Phase CO-9, Module 5)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_health import (
    audit_duration_percentiles,
    claude_path_label,
    last_audit_run,
    last_claude_call,
    system_alerts,
)
from app.auth import CurrentUser
from app.config import get_settings
from app.db.models.audit_events import AuditEvent
from app.db.models.cron_run_log import CronRunLog
from app.db.session import get_session
from app.knowledge import health as retrieval_health
from app.knowledge.client import get_client
from app.routes.admin._deps import admin_user, iso

router = APIRouter(tags=["v1-admin"])


def _pool_stats() -> dict:
    try:
        from app.db.base import engine

        pool = engine.pool
        return {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception:  # noqa: BLE001 — pool internals vary by driver/pool class
        return {"size": None, "checked_out": None, "overflow": None}


KNOWLEDGE_TOOL_PREFIX = "qdrant_search_"
RETRIEVAL_WINDOW = 50
CRON_FAILURE_LOOKBACK_DAYS = 7


async def _retrieval_signal(session: AsyncSession) -> dict[str, Any]:
    """``retrieval_degraded`` (e2e 2026-09-23 B1): the live per-process ledger PLUS the
    durable last-N knowledge-tool outcomes from the audit-event trail (survives a restart,
    covers every replica). Qdrant "healthy" said nothing while every search failed."""
    rows = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.event_type == "tool_invocation")
                .order_by(AuditEvent.timestamp.desc())
                .limit(400)
            )
        )
        .scalars()
        .all()
    )
    recent = []
    for ev in rows:
        tools = [str(x) for x in (ev.tools_invoked or [])]
        if any(x.startswith(KNOWLEDGE_TOOL_PREFIX) for x in tools):
            recent.append(ev)
        if len(recent) >= RETRIEVAL_WINDOW:
            break
    errors = [ev for ev in recent if ev.outcome != "success" or ev.error_details]
    live = retrieval_health.snapshot()
    durable_rate = round(len(errors) / len(recent), 3) if recent else 0.0
    if live["status"] == "degraded" or (recent and durable_rate >= retrieval_health.DEGRADED_ERROR_RATE):
        status = "degraded"
    elif recent or live["status"] == "healthy":
        status = "healthy"
    else:
        status = "unknown"
    last_error = errors[0] if errors else None
    return {
        "status": status,
        "live": live,
        "durable": {
            "window": RETRIEVAL_WINDOW,
            "calls": len(recent),
            "errors": len(errors),
            "error_rate": durable_rate,
            "last_error_at": iso(last_error.timestamp) if last_error else None,
            "last_error": (last_error.error_details or "")[:200] if last_error else None,
        },
    }


async def _failed_crons(session: AsyncSession) -> list[dict[str, Any]]:
    """Cron runs that did not succeed in the last week — `cms_ncd_lcd_bulk` failed on 9/19
    and nothing surfaced it (readiness B2). Latest failed run per cron."""
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=CRON_FAILURE_LOOKBACK_DAYS)
    rows = (
        (
            await session.execute(
                select(CronRunLog)
                .where(CronRunLog.started_at >= since)
                .where(CronRunLog.status.in_(("failed", "partial", "interrupted")))
                .order_by(CronRunLog.started_at.desc())
            )
        )
        .scalars()
        .all()
    )
    seen: set[str] = set()
    out = []
    for r in rows:
        if r.cron_name in seen:
            continue
        seen.add(r.cron_name)
        out.append(
            {
                "cron_name": r.cron_name,
                "status": r.status,
                "started_at": iso(r.started_at),
                "finished_at": iso(r.finished_at),
                "error": (getattr(r, "error_message", None) or "")[:200] or None,
            }
        )
    return out


def _alerts(retrieval: dict[str, Any], failed_crons: list[dict[str, Any]], system: dict) -> list[dict[str, Any]]:
    """The alert path (readiness B2): ONE list the pager reads. Each entry is a thing a
    person must act on, with what to do."""
    alerts: list[dict[str, Any]] = []
    if retrieval["status"] == "degraded":
        voyage = retrieval["live"].get("voyage") or {}
        last = {k: v.get("last_status") for k, v in voyage.items()}
        alerts.append(
            {
                "kind": "retrieval_degraded",
                "severity": "high",
                "detail": (
                    f"{retrieval['durable']['errors']} of the last {retrieval['durable']['calls']} "
                    f"knowledge-tool calls failed (Voyage last statuses: {last or 'n/a'}) — audits "
                    "are running without the rules corpus; legal claims are being downgraded"
                ),
                "action": "check the Voyage AI account (429 = per-minute quota / payment method) and the runtime log line retrieval.degraded",
                "at": retrieval["durable"]["last_error_at"] or retrieval["live"].get("last_alert_at"),
            }
        )
    for c in failed_crons:
        alerts.append(
            {
                "kind": "cron_failed",
                "severity": "medium",
                "detail": f"{c['cron_name']} {c['status']} at {c['started_at']}" + (f": {c['error']}" if c.get("error") else ""),
                "action": "open Admin › System › crons, read the run, re-trigger once fixed",
                "at": c["started_at"],
            }
        )
    if int(system.get("count") or 0) > 0:
        alerts.append(
            {
                "kind": "system_error",
                "severity": "high",
                "detail": f"{system['count']} audit(s) ended in system_error since this replica started",
                "action": "read Recent errors below; the user was told the team has been notified — make that true",
                "at": system.get("last_at"),
            }
        )
    return alerts


@router.get("/admin/system/health")
async def system_health(
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    settings = get_settings()

    # Claude path health (foundry | anthropic-direct | stub). Under Foundry managed
    # identity (DL-79) an unset ANTHROPIC_API_KEY is the CORRECT prod state, not a
    # "stub". last_claude_call (below) reports whether the MOST RECENT real Claude
    # call actually succeeded — set by the chat + audit paths and scripts/foundry_smoke.py.
    # That's what catches a broken token scope that a "config looks fine" check wouldn't.
    anthropic_status = claude_path_label(settings)

    qdrant_status = "healthy"
    try:
        await get_client().get_collections()
    except Exception:  # noqa: BLE001
        qdrant_status = "down"

    errs = (
        (
            await session.execute(
                select(AuditEvent)
                .where(or_(AuditEvent.outcome != "success", AuditEvent.error_details.isnot(None)))
                .order_by(AuditEvent.timestamp.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    retrieval = await _retrieval_signal(session)
    failed_crons = await _failed_crons(session)
    alerts_now = system_alerts()

    return {
        "deploy_sha": os.environ.get("DEPLOY_SHA") or os.environ.get("GIT_SHA"),
        "deploy_timestamp": os.environ.get("DEPLOY_TIMESTAMP"),
        "db_pool": _pool_stats(),
        "qdrant_status": qdrant_status,
        "anthropic_status": anthropic_status,
        "last_claude_call": last_claude_call(),
        # Item 1 — last real-agent audit run (duration, terminal reason, regen count, stage
        # timings), next to the Claude-call health.
        "last_audit_run": last_audit_run(),
        # Item 2 — p50/p95 audit wall-clock over recent runs (per-replica).
        "audit_duration_percentiles": audit_duration_percentiles(),
        # HP-1 — count of system_error audit terminations ("our team has been notified").
        "system_alerts": alerts_now,
        # e2e 2026-09-23 B1 — retrieval_degraded: live ledger + durable last-N tool outcomes.
        "retrieval": retrieval,
        # readiness B2 — failed crons in the last week, and the ONE alert list a pager reads.
        "failed_crons": failed_crons,
        "alerts": _alerts(retrieval, failed_crons, alerts_now),
        "recent_errors": [
            {
                "event_id": str(e.event_id),
                "timestamp": iso(e.timestamp),
                "event_type": e.event_type,
                "actor": e.actor,
                "outcome": e.outcome,
                "error": e.error_details,
            }
            for e in errs
        ],
        "runtime_version": "0.1.0",
        "node_env": settings.node_env,
    }
