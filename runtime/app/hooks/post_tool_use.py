"""PostToolUse hook — writes an audit_events row.

Per the contract the hook is semantically void and raises on a write failure. The
payload is AES-256-GCM encrypted via app.security.audit_crypto when AUDIT_LOG_ENC_KEY
is configured (key_version = configured version); without a key (dev) it falls back
to clear-text JSON bytes with key_version 0, which readers decode transparently. The
payload_hash is always over the CLEAR-TEXT bytes (integrity check independent of the
key). Ops alerting on failure lands later.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.hooks.contracts import PostToolUseInput
from app.security.audit_writer import build_audit_event


async def post_tool_use_hook(inp: PostToolUseInput, session: AsyncSession) -> None:
    event = build_audit_event(
        event_type="tool_invocation",
        actor=inp.actor,
        case_file_id=inp.case_file_id,
        payload={
            "actor": inp.actor,
            "tool_name": inp.tool_name,
            "tool_args_scrubbed": inp.tool_args_scrubbed,
            "tool_result": inp.tool_result,
            "duration_ms": inp.duration_ms,
            "outcome": inp.outcome,
            "error_details": inp.error_details,
        },
        tools_invoked=[inp.tool_name],
        outcome=inp.outcome,
        error_details=inp.error_details,
    )
    session.add(event)
    await session.flush()  # raise-on-error per the void contract; caller commits
