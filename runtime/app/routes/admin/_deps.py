"""Shared admin-route helpers (Phase CO-9).

Admin gate (DL-60: non-admin → 404, anti-enumeration), uuid/iso coercion, audit-payload
decode, and the canonical admin-action audit writer used by every admin module.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.audit_events import AuditEvent
from app.security.audit_writer import build_audit_event


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
    """Decrypt + JSON-decode an audit payload (Phase 2.2). decrypt_payload transparently
    handles both key_version 0 (clear-text — dev/legacy rows) and AES-256-GCM rows."""
    from app.security.audit_crypto import AuditCryptoError, decrypt_payload

    try:
        plaintext = decrypt_payload(bytes(ev.payload_encrypted), ev.key_version)
        return json.loads(plaintext.decode("utf-8"))
    except (AuditCryptoError, ValueError, UnicodeDecodeError, TypeError):
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

    Convention: actor = acting admin's USER ID, user_id = the TARGET user (so the HIPAA
    "every access of patient X" query filters the indexed column). MEDIUM-5 (2026-08-19
    security review): the actor column is cleartext — staff email is PII, so the UUID
    goes there and the email rides only in the ENCRYPTED payload (acting_admin_email).
    Rows written before this change carry emails; the admin_id filter matches both.
    """
    payload = {
        "action": action,
        "acting_admin_id": str(admin.user_id),
        "acting_admin_email": admin.email,
        "target_user_id": str(target_user_id) if target_user_id else None,
        **(extra or {}),
    }
    session.add(
        build_audit_event(
            event_type="user_action",
            actor=str(admin.user_id),  # UUID in the cleartext column (convention above)
            user_id=target_user_id,
            case_file_id=case_file_id,
            payload=payload,
            tools_invoked=None,
            outcome=outcome,
        )
    )
