"""Admin user management (Phase CO-9, Module 1).

Block / unblock / reset-onboarding / force-logout / send-magic-link / soft-delete /
set-role, plus list + detail + per-user audit log. Every mutation writes an audit row and
(where it should revoke sessions) bumps users.jwt_version.

DL-60: non-admin → 404. DL-47: the magic-link body carries only the auth token (no PHI),
so it reuses the same send path as the user-facing flow.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.auth.jwt import create_magic_link_token
from app.auth.sendgrid import send_magic_link_email
from app.config import get_settings
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.db.session import get_session
from app.routes.admin._deps import admin_user, admin_uuid, audit_admin_action, decode_payload, iso

router = APIRouter(tags=["v1-admin"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status(u: User) -> str:
    if u.soft_deleted_at is not None:
        return "soft_deleted"
    return "blocked" if u.is_blocked else "active"


def _touch(u: User) -> None:
    u.last_admin_action_at = _now()
    u.updated_at = _now()


async def _load_user(session: AsyncSession, user_id: str) -> User:
    u = (
        await session.execute(select(User).where(User.user_id == admin_uuid(user_id)))
    ).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return u


async def _case_counts(session: AsyncSession, user_ids: list) -> dict:
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(CaseFile.user_id, func.count())
            .where(CaseFile.user_id.in_(user_ids))
            .group_by(CaseFile.user_id)
        )
    ).all()
    return {uid: n for uid, n in rows}


def _user_summary(u: User, case_count: int) -> dict:
    return {
        "user_id": str(u.user_id),
        "email": u.email,
        "user_type": u.user_type,
        "status": _status(u),
        "created_at": iso(u.created_at),
        "last_admin_action_at": iso(u.last_admin_action_at),
        "case_file_count": case_count,
    }


# --------------------------------------------------------------------------- #
# List + detail
# --------------------------------------------------------------------------- #
@router.get("/admin/users")
async def list_users(
    q: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    query = select(User)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(User.email).like(like), User.user_id.cast(String).ilike(like))
        )
    if status == "active":
        query = query.where(User.is_blocked.is_(False), User.soft_deleted_at.is_(None))
    elif status == "blocked":
        query = query.where(User.is_blocked.is_(True))
    elif status == "soft_deleted":
        query = query.where(User.soft_deleted_at.isnot(None))

    query = (
        query.order_by(User.created_at.desc()).limit(min(max(limit, 1), 200)).offset(max(offset, 0))
    )
    rows = (await session.execute(query)).scalars().all()
    counts = await _case_counts(session, [u.user_id for u in rows])
    return {
        "users": [_user_summary(u, counts.get(u.user_id, 0)) for u in rows],
        "count": len(rows),
    }


@router.get("/admin/users/{user_id}")
async def user_detail(
    user_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    cases = (
        (
            await session.execute(
                select(CaseFile)
                .where(CaseFile.user_id == u.user_id)
                .order_by(CaseFile.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    last_activity = max((c.updated_at for c in cases), default=None)
    return {
        "user_id": str(u.user_id),
        "email": u.email,
        "user_type": u.user_type,
        "status": _status(u),
        "is_blocked": u.is_blocked,
        "blocked_at": iso(u.blocked_at),
        "blocked_by": str(u.blocked_by) if u.blocked_by else None,
        "blocked_reason": u.blocked_reason,
        "soft_deleted_at": iso(u.soft_deleted_at),
        "soft_deleted_by": str(u.soft_deleted_by) if u.soft_deleted_by else None,
        "jwt_version": u.jwt_version,
        "service_consent": u.service_consent,
        "improvement_consent": u.improvement_consent,
        "created_at": iso(u.created_at),
        "updated_at": iso(u.updated_at),
        "last_admin_action_at": iso(u.last_admin_action_at),
        # last_login isn't a persisted column in V1-Lite; last_activity proxies it.
        "last_activity_at": iso(last_activity),
        "case_file_count": len(cases),
        "recent_case_files": [
            {
                "case_file_id": str(c.case_file_id),
                "status": c.status,
                "intake_status": c.intake_status,
                "created_at": iso(c.created_at),
            }
            for c in cases[:5]
        ],
        # No provider/sanctions model in V1-Lite yet.
        "active_provider_sanctions": [],
    }


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
class BlockRequest(BaseModel):
    reason: str


@router.post("/admin/users/{user_id}/block")
async def block_user(
    user_id: str,
    req: BlockRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    u.is_blocked = True
    u.blocked_at = _now()
    u.blocked_by = admin.user_id
    u.blocked_reason = req.reason
    u.jwt_version = (u.jwt_version or 1) + 1  # force-logout side effect
    _touch(u)
    await audit_admin_action(
        session, admin=admin, action="block", target_user_id=u.user_id, extra={"reason": req.reason}
    )
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "status": _status(u)}


@router.post("/admin/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    u.is_blocked = False
    u.blocked_at = None
    u.blocked_by = None
    u.blocked_reason = None
    _touch(u)  # NOTE: no jwt_version bump — user gets back in via the existing flow
    await audit_admin_action(session, admin=admin, action="unblock", target_user_id=u.user_id)
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "status": _status(u)}


@router.post("/admin/users/{user_id}/reset-onboarding")
async def reset_onboarding(
    user_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    cases = (
        (await session.execute(select(CaseFile).where(CaseFile.user_id == u.user_id)))
        .scalars()
        .all()
    )
    for c in cases:
        c.intake_status = "not_started"  # does NOT delete case files
    u.jwt_version = (u.jwt_version or 1) + 1  # force re-onboard on next login
    _touch(u)
    await audit_admin_action(
        session,
        admin=admin,
        action="reset_onboarding",
        target_user_id=u.user_id,
        extra={"cases_reset": len(cases)},
    )
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "cases_reset": len(cases)}


@router.post("/admin/users/{user_id}/force-logout")
async def force_logout(
    user_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    u.jwt_version = (u.jwt_version or 1) + 1
    _touch(u)
    await audit_admin_action(session, admin=admin, action="force_logout", target_user_id=u.user_id)
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "jwt_version": u.jwt_version}


@router.post("/admin/users/{user_id}/send-magic-link")
async def admin_send_magic_link(
    user_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    if u.soft_deleted_at is not None:
        raise HTTPException(status_code=400, detail="cannot send to a deleted user")
    settings = get_settings()
    token, _jti = create_magic_link_token(u.email, return_url=None)
    magic_link_url = f"{settings.magic_link_base_url}/v1/auth/magic-link-verify?token={token}"
    # DL-47: body carries only the token (no PHI); same send path as the user-facing flow.
    await send_magic_link_email(u.email, magic_link_url)
    await audit_admin_action(
        session, admin=admin, action="send_magic_link", target_user_id=u.user_id
    )
    _touch(u)
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "sent_to_domain": u.email.split("@")[-1]}


@router.post("/admin/users/{user_id}/soft-delete")
async def soft_delete_user(
    user_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    if u.soft_deleted_at is not None:
        return {"ok": True, "user_id": str(u.user_id), "status": "soft_deleted"}
    # Anonymize the email; preserve user_id, case files, and the audit trail (HIPAA
    # retention). No display_name column exists in V1-Lite — the derived first-name comes
    # from the (now anonymized) email, so it's covered.
    digest = hashlib.sha256((u.email or "").encode("utf-8")).hexdigest()[:8]
    u.email = f"deleted-{digest}@deleted.tyndaleapp.net"
    u.phone = None
    u.soft_deleted_at = _now()
    u.soft_deleted_by = admin.user_id
    u.jwt_version = (u.jwt_version or 1) + 1
    _touch(u)
    await audit_admin_action(session, admin=admin, action="soft_delete", target_user_id=u.user_id)
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "status": "soft_deleted"}


class SetRoleRequest(BaseModel):
    role: Literal["admin", "user"]


@router.post("/admin/users/{user_id}/set-role")
async def set_role(
    user_id: str,
    req: SetRoleRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Toggle a user between 'admin' and 'user'. Admin gating reads user_type live each
    request, so the change takes effect immediately (no jwt bump needed). An admin cannot
    demote themselves (self-lockout guard)."""
    u = await _load_user(session, user_id)
    if u.user_id == admin.user_id and req.role != "admin":
        raise HTTPException(status_code=400, detail="cannot remove your own admin role")
    previous = u.user_type
    u.user_type = req.role
    _touch(u)
    await audit_admin_action(
        session,
        admin=admin,
        action="set_role",
        target_user_id=u.user_id,
        extra={"from": previous, "to": req.role},
    )
    await session.commit()
    return {"ok": True, "user_id": str(u.user_id), "user_type": u.user_type}


# --------------------------------------------------------------------------- #
# Per-user audit log
# --------------------------------------------------------------------------- #
@router.get("/admin/users/{user_id}/audit-log")
async def user_audit_log(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    u = await _load_user(session, user_id)
    rows = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.user_id == u.user_id)
                .order_by(AuditEvent.timestamp.desc())
                .limit(min(max(limit, 1), 200))
                .offset(max(offset, 0))
            )
        )
        .scalars()
        .all()
    )
    return {
        "user_id": str(u.user_id),
        "entries": [
            {
                "event_id": str(ev.event_id),
                "timestamp": iso(ev.timestamp),
                "event_type": ev.event_type,
                "actor": ev.actor,
                "action": decode_payload(ev).get("action"),
                "outcome": ev.outcome,
            }
            for ev in rows
        ],
        "count": len(rows),
    }
