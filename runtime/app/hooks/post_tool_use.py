"""PostToolUse hook — STUB (Phase 1C).

Writes an audit_events row. Per the contract the hook is semantically void and
raises on a write failure. Phase 1C writes a CLEAR-TEXT JSON payload as the
`payload_encrypted` bytes (TODO Phase 4: AES-GCM via Azure Key Vault) and uses
key_version=0. Ops alerting on failure also lands in Phase 4.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_events import AuditEvent
from app.hooks.contracts import PostToolUseInput


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
    payload_hash = hashlib.sha256(payload_bytes).digest()

    event = AuditEvent(
        event_type="tool_invocation",
        actor=inp.actor,
        case_file_id=inp.case_file_id,
        # TODO(Phase 4): encrypt with AES-GCM; for now store clear-text JSON bytes.
        payload_encrypted=payload_bytes,
        payload_hash=payload_hash,
        key_version=0,  # placeholder; real Key Vault versions in Phase 4
        tools_invoked=[inp.tool_name],
        outcome=inp.outcome,
        error_details=inp.error_details,
    )
    session.add(event)
    await session.flush()  # raise-on-error per the void contract; caller commits
