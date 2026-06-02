"""Admin cron control (Phase CO-9, Module 5) — list, manual-trigger, run history.

A manual trigger records a cron_run_log row (triggered_source='manual_admin') synchronously
+ audits it, then runs the cron in the background and updates the row on completion. The
trigger returns immediately with the run_id (status='running').
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.crons.registry import CRON_REGISTRY
from app.db.base import AsyncSessionLocal
from app.db.models.cron_run_log import CronRunLog
from app.db.session import get_session
from app.routes.admin._deps import admin_user, admin_uuid, audit_admin_action, iso

router = APIRouter(tags=["v1-admin"])

_tasks: set[asyncio.Task] = set()


def _run_dict(r: CronRunLog) -> dict:
    return {
        "run_id": str(r.run_id),
        "cron_name": r.cron_name,
        "started_at": iso(r.started_at),
        "finished_at": iso(r.finished_at),
        "status": r.status,
        "triggered_source": r.triggered_source,
        "triggered_by": str(r.triggered_by) if r.triggered_by else None,
        "summary_json": r.summary_json,
        "error_message": r.error_message,
    }


async def _run_and_record(name: str, run_id) -> None:
    status, err, summary = "success", None, None
    try:
        result = await CRON_REGISTRY[name]["fn"]()
        summary = result if isinstance(result, dict) else {"result": str(result)}
    except Exception as e:  # noqa: BLE001 — captured into the run log, never propagated
        status, err = "failed", str(e)
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(select(CronRunLog).where(CronRunLog.run_id == run_id))
        ).scalar_one_or_none()
        if row:
            row.finished_at = datetime.datetime.now(datetime.timezone.utc)
            row.status = status
            row.summary_json = summary
            row.error_message = err
            await s.commit()


@router.get("/admin/crons")
async def list_crons(
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    out: list[dict] = []
    for name, meta in CRON_REGISTRY.items():
        last = (
            await session.execute(
                select(CronRunLog)
                .where(CronRunLog.cron_name == name)
                .order_by(CronRunLog.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(
            {
                "cron_name": name,
                "schedule": meta["schedule"],
                "last_run_at": iso(last.started_at) if last else None,
                "last_status": last.status if last else None,
                "currently_running": bool(last and last.status == "running"),
            }
        )
    return {"crons": out}


@router.post("/admin/crons/{name}/trigger")
async def trigger_cron(
    name: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if name not in CRON_REGISTRY:
        raise HTTPException(status_code=404, detail="Not Found")
    row = CronRunLog(
        cron_name=name,
        status="running",
        triggered_source="manual_admin",
        triggered_by=admin.user_id,
    )
    session.add(row)
    await session.flush()
    run_id = row.run_id
    await audit_admin_action(
        session, admin=admin, action="cron_trigger", extra={"cron_name": name, "run_id": str(run_id)}
    )
    await session.commit()

    task = asyncio.create_task(_run_and_record(name, run_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"run_id": str(run_id), "status": "running"}


@router.get("/admin/crons/{name}/runs")
async def cron_runs(
    name: str,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = (
        (
            await session.execute(
                select(CronRunLog)
                .where(CronRunLog.cron_name == name)
                .order_by(CronRunLog.started_at.desc())
                .limit(min(max(limit, 1), 200))
                .offset(max(offset, 0))
            )
        )
        .scalars()
        .all()
    )
    return {"cron_name": name, "runs": [_run_dict(r) for r in rows], "count": len(rows)}


@router.get("/admin/crons/{name}/runs/{run_id}")
async def cron_run_detail(
    name: str,
    run_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = (
        await session.execute(select(CronRunLog).where(CronRunLog.run_id == admin_uuid(run_id)))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return _run_dict(row)
