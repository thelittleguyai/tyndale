"""Admin audit-log viewer (Phase CO-9, Module 4).

HIPAA accountability: "show me every access of patient X's data" → filter by user_id (the
target, an indexed column). Also filterable by acting admin, action type, tool, and date
range; exportable as a full result set.

Audit payloads are clear-text JSON bytes (Phase 1C), so the payload column isn't
JSONB-queryable — action_type is post-filtered in Python; user_id / actor / date / tool are
SQL-filtered. The list path caps the SQL scan; export raises the cap for completeness.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.audit_events import AuditEvent
from app.db.models.users import User
from app.db.session import get_session
from app.routes.admin._deps import admin_user, admin_uuid, decode_payload, iso

router = APIRouter(tags=["v1-admin"])

_LIST_CAP = 2000
_EXPORT_CAP = 50000


async def _query(
    session: AsyncSession,
    *,
    user_id: str | None,
    admin_id: str | None,
    tool_name: str | None,
    date_from: str | None,
    date_to: str | None,
    cap: int,
) -> list[AuditEvent]:
    stmt = select(AuditEvent)
    if user_id:
        stmt = stmt.where(AuditEvent.user_id == admin_uuid(user_id))
    if admin_id:
        # MEDIUM-5 (2026-08-19): new rows carry the admin's UUID in actor; rows written
        # before the change carry the email. Match either so history stays filterable.
        email = (
            await session.execute(select(User.email).where(User.user_id == admin_uuid(admin_id)))
        ).scalar_one_or_none()
        stmt = stmt.where(
            AuditEvent.actor.in_([str(admin_uuid(admin_id)), email or "__no_such_admin__"])
        )
    if tool_name:
        stmt = stmt.where(AuditEvent.tools_invoked.cast(String).ilike(f"%{tool_name}%"))
    for raw, lower in ((date_from, True), (date_to, False)):
        if raw:
            try:
                dt = datetime.datetime.fromisoformat(raw)
            except ValueError:
                raise HTTPException(status_code=422, detail="invalid date (ISO-8601)") from None
            stmt = stmt.where(AuditEvent.timestamp >= dt if lower else AuditEvent.timestamp <= dt)
    stmt = stmt.order_by(AuditEvent.timestamp.desc()).limit(cap)
    return list((await session.execute(stmt)).scalars().all())


def _entry(ev: AuditEvent, payload: dict) -> dict:
    return {
        "event_id": str(ev.event_id),
        "timestamp": iso(ev.timestamp),
        "event_type": ev.event_type,
        "actor": ev.actor,
        "target_user_id": str(ev.user_id) if ev.user_id else None,
        "case_file_id": str(ev.case_file_id) if ev.case_file_id else None,
        "action": payload.get("action"),
        "tools_invoked": ev.tools_invoked,
        "outcome": ev.outcome,
        "payload": payload,
    }


@router.get("/admin/audit-log")
async def audit_log(
    user_id: str | None = None,
    admin_id: str | None = None,
    action_type: str | None = None,
    tool_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await _query(
        session,
        user_id=user_id,
        admin_id=admin_id,
        tool_name=tool_name,
        date_from=date_from,
        date_to=date_to,
        cap=_LIST_CAP,
    )
    decoded = [(ev, decode_payload(ev)) for ev in rows]
    if action_type:
        decoded = [(ev, p) for ev, p in decoded if p.get("action") == action_type]
    total = len(decoded)
    start = max(offset, 0)
    page = decoded[start : start + min(max(limit, 1), 200)]
    return {
        "entries": [_entry(ev, p) for ev, p in page],
        "count": len(page),
        "total_matched": total,
        "capped": len(rows) >= _LIST_CAP,
    }


@router.get("/admin/audit-log/export")
async def audit_log_export(
    user_id: str | None = None,
    admin_id: str | None = None,
    action_type: str | None = None,
    tool_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Full filtered result set for a HIPAA access report (no pagination)."""
    rows = await _query(
        session,
        user_id=user_id,
        admin_id=admin_id,
        tool_name=tool_name,
        date_from=date_from,
        date_to=date_to,
        cap=_EXPORT_CAP,
    )
    decoded = [(ev, decode_payload(ev)) for ev in rows]
    if action_type:
        decoded = [(ev, p) for ev, p in decoded if p.get("action") == action_type]
    return {
        "exported_at": iso(datetime.datetime.now(datetime.timezone.utc)),
        "filters": {
            "user_id": user_id,
            "admin_id": admin_id,
            "action_type": action_type,
            "tool_name": tool_name,
            "date_from": date_from,
            "date_to": date_to,
        },
        "count": len(decoded),
        "entries": [_entry(ev, p) for ev, p in decoded],
    }
