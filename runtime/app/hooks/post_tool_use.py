"""PostToolUse hook — writes an audit_events row.

Per the contract the hook is semantically void and raises on a write failure. The
payload is AES-256-GCM encrypted via app.security.audit_crypto when AUDIT_LOG_ENC_KEY
is configured (key_version = configured version); without a key (dev) it falls back
to clear-text JSON bytes with key_version 0, which readers decode transparently. The
payload_hash is always over the CLEAR-TEXT bytes (integrity check independent of the
key). Ops alerting on failure lands later.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_events import AuditEvent
from app.hooks.contracts import PostToolUseInput
from app.security.audit_crypto import encrypt_payload


async def post_tool_use_hook(inp: PostToolUseInput, session: AsyncSession) -> None:
    payload = {
        "actor": inp.actor,
        "tool_name": inp.tool_name,
        "tool_args_scrubbed": inp.tool_args_scrubbed,
        "tool_result": inp.tool_result,
        "duration_ms": inp.duration_ms,
        "outcome": inp.outcome,
        "error_details": inp.error_details,
    }
    payload_bytes = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    payload_hash = hashlib.sha256(payload_bytes).digest()  # over clear-text (integrity)
    stored_bytes, key_version = encrypt_payload(payload_bytes)

    event = AuditEvent(
        event_type="tool_invocation",
        actor=inp.actor,
        case_file_id=inp.case_file_id,
        # AES-GCM ciphertext when AUDIT_LOG_ENC_KEY is set; clear-text JSON otherwise.
        payload_encrypted=stored_bytes,
        payload_hash=payload_hash,
        key_version=key_version,
        tools_invoked=[inp.tool_name],
        outcome=inp.outcome,
        error_details=inp.error_details,
    )
    session.add(event)
    await session.flush()  # raise-on-error per the void contract; caller commits
