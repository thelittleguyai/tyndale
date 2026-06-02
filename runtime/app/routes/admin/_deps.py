"""Shared admin-route helpers (Phase CO-9).

Admin gate (DL-60: non-admin → 404, anti-enumeration), uuid/iso coercion, audit-payload
decode, and the canonical admin-action audit writer used by every admin module.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.audit_events import AuditEvent


async def admin_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """DL-60: every admin route requires user_type=='admin'; a non-admin gets 404, never
    403 — the console's existence is never revealed."""
    if user.user_type != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    return user


def admin_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as e:
        raise HTTPException(status_code=404, detail="Not Found") from e


def iso(dt: datetime.datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def decode_payload(ev: AuditEvent) -> dict:
    """Phase-1C audit payloads are clear-text JSON bytes (AES-GCM in Phase 4)."""
    try:
        return json.loads(bytes(ev.payload_encrypted).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, TypeError):
        return {}


async def audit_admin_action(
    session: AsyncSession,
    *,
    admin: CurrentUser,
    action: str,
    target_user_id: uuid.UUID | None = None,
    case_file_id: uuid.UUID | None = None,
    extra: dict[str, Any] | None = None,
    outcome: str = "success",
) -> None:
    """Write one admin-action audit row (does NOT commit — caller owns the txn).

    Convention: actor = acting admin's email, user_id = the TARGET user (so the HIPAA
    "every access of patient X" query filters the indexed column), and the acting admin's
    id is duplicated into the payload for the admin_id filter.
    """
    payload = {
        "action": action,
        "acting_admin_id": str(admin.user_id),
        "acting_admin_email": admin.email,
        "target_user_id": str(target_user_id) if target_user_id else None,
        **(extra or {}),
    }
    body = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    session.add(
        AuditEvent(
            event_type="user_action",
            actor=admin.email,
            user_id=target_user_id,
            case_file_id=case_file_id,
            payload_encrypted=body,
            payload_hash=hashlib.sha256(body).digest(),
            key_version=0,
            tools_invoked=None,
            outcome=outcome,
        )
    )
