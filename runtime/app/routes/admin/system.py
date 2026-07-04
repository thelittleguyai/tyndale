"""Admin system health (Phase CO-9, Module 5)."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_health import claude_path_label, last_claude_call
from app.auth import CurrentUser
from app.config import get_settings
from app.db.models.audit_events import AuditEvent
from app.db.session import get_session
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

    return {
        "deploy_sha": os.environ.get("DEPLOY_SHA") or os.environ.get("GIT_SHA"),
        "deploy_timestamp": os.environ.get("DEPLOY_TIMESTAMP"),
        "db_pool": _pool_stats(),
        "qdrant_status": qdrant_status,
        "anthropic_status": anthropic_status,
        "last_claude_call": last_claude_call(),
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
