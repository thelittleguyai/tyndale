"""Single canonical audit-event envelope (Phase 2.2).

Every AuditEvent is built here: a plain payload dict → JSON bytes → SHA-256 over the
CLEAR-TEXT bytes (integrity, independent of encryption) → encrypt_payload (AES-256-GCM when
a key is configured, else clear-text at key_version 0) → AuditEvent. Routing every write
through this one helper means no site can silently bypass encryption. Callers add the
returned event to their own session (this does not touch the DB).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.db.models.audit_events import AuditEvent
from app.security.audit_crypto import encrypt_payload


def build_audit_event(
    *,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    outcome: str,
    user_id: uuid.UUID | None = None,
    case_file_id: uuid.UUID | None = None,
    tools_invoked: list[str] | None = None,
    error_details: str | None = None,
) -> AuditEvent:
    """Build an encrypted AuditEvent. ``payload`` is the clear-text dict to protect;
    ``actor`` identifies who acted — a subagent name, a user UUID, a system-process id, or
    (admin-action rows only) the acting admin's email. Member/chat rows use the user UUID,
    never the member's email (that is PII)."""
    body = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    payload_hash = hashlib.sha256(body).digest()
    stored, key_version = encrypt_payload(body)
    return AuditEvent(
        event_type=event_type,
        actor=actor,
        user_id=user_id,
        case_file_id=case_file_id,
        payload_encrypted=stored,
        payload_hash=payload_hash,
        key_version=key_version,
        tools_invoked=tools_invoked,
        outcome=outcome,
        error_details=error_details,
    )
