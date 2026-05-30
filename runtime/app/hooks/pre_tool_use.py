"""PreToolUse hook — Phase 1C stub + Phase CO-8 send_email PHI guardrail.

Presidio scrubbing of tool *args* still lands in Phase 4. This module enforces
the non-scrubbing invariants so they hold pre-Presidio:
  1. Effective-date filter required on the date-filtered Qdrant searches.
  2. Approval token required for gated tools (send_email, doc_generate).
  3. (CO-8 / DL-47) send_email content must be PHI-free: an allowlisted template
     OR a clean deep PHI scan of subject+body. A block writes a `phi_block`
     audit_events row (via the async ``guard_send_email``) and returns
     approved=False — it NEVER raises (no 500 on PHI detection).

Decision vs. audit are split on purpose: ``evaluate_send_email`` is a pure,
session-less decision (easy to unit-test); ``guard_send_email`` is the async,
audited path the runtime calls when a DB session is available.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email_templates import is_allowlisted
from app.auth.phi_patterns import PhiMatch, detect_phi
from app.db.models.audit_events import AuditEvent
from app.hooks.contracts import PreToolUseInput, PreToolUseResult

DATE_FILTERED_TOOLS = {"qdrant_search_laws_regulations", "qdrant_search_payer_policies"}
GATED_TOOLS = {"send_email", "doc_generate"}

_PHI_BLOCK_REASON = (
    "send_email blocked: detected potential PHI in content ({n} pattern matches). "
    "Use an allowlisted template_id from runtime/app/auth/email_templates.py "
    "ALLOWED_TEMPLATE_IDS, or remove the PHI-suggesting content from subject/body. "
    "See DL-47."
)


def _combined(tool_args: dict) -> str:
    subject = tool_args.get("subject", "") or ""
    body = tool_args.get("body", "") or ""
    return f"{subject}\n\n{body}"


def scan_send_email(tool_args: dict) -> list[PhiMatch]:
    """PHI matches for a send_email payload. Returns [] when an allowlisted
    template is used (deep scan skipped — vetted PHI-free) or the content is
    genuinely clean. Pure: no DB, no session."""
    if is_allowlisted(tool_args.get("template_id")):
        return []
    return detect_phi(_combined(tool_args))


def evaluate_send_email(tool_args: dict) -> PreToolUseResult:
    """DL-47 content guardrail decision for send_email (pure, session-less).

    approved=True for an allowlisted template or a clean scan; approved=False
    (with a DL-47 block_reason) when any PHI pattern is present."""
    matches = scan_send_email(tool_args)
    if matches:
        return PreToolUseResult(
            sanitized_args=tool_args,
            approved=False,
            block_reason=_PHI_BLOCK_REASON.format(n=len(matches)),
        )
    return PreToolUseResult(sanitized_args=tool_args, approved=True, block_reason=None)


def pre_tool_use_hook(inp: PreToolUseInput) -> PreToolUseResult:
    # Rule 3 (contract): point-in-time filter is mandatory on these searches.
    if inp.tool_name in DATE_FILTERED_TOOLS and not inp.tool_args.get("effective_date"):
        return PreToolUseResult(
            sanitized_args=inp.tool_args,
            approved=False,
            block_reason=f"{inp.tool_name} requires an 'effective_date' filter (point-in-time rule)",
        )

    # Rule 4 (CO-8 / DL-47): send_email may never carry PHI. Checked BEFORE the
    # approval-token gate so a PHI block is reported even when no token is present
    # (PHI content is the more critical invariant).
    if inp.tool_name == "send_email":
        phi = evaluate_send_email(inp.tool_args)
        if not phi.approved:
            return phi

    # Rule 2 (contract): gated tools require a user-approval token.
    if inp.tool_name in GATED_TOOLS and not inp.tool_args.get("approval_token"):
        return PreToolUseResult(
            sanitized_args=inp.tool_args,
            approved=False,
            block_reason=f"{inp.tool_name} requires an 'approval_token' (user-approval gate)",
        )

    # STUB: Presidio arg-scrubbing (Rule 1) is a no-op until Phase 4.
    return PreToolUseResult(sanitized_args=inp.tool_args, approved=True, block_reason=None)


async def guard_send_email(inp: PreToolUseInput, session: AsyncSession) -> PreToolUseResult:
    """Audited send_email guardrail (DL-47).

    Runs the content check and, on a PHI block, writes a ``phi_block``
    audit_events row before returning approved=False. This is the path the
    runtime calls when a DB session is available. It NEVER raises on PHI
    detection — a blocked send is a normal, audited outcome (approved=False),
    not a 500."""
    matches = scan_send_email(inp.tool_args)
    if not matches:
        return PreToolUseResult(sanitized_args=inp.tool_args, approved=True, block_reason=None)

    await _write_phi_block_audit(inp, matches, session)
    return PreToolUseResult(
        sanitized_args=inp.tool_args,
        approved=False,
        block_reason=_PHI_BLOCK_REASON.format(n=len(matches)),
    )


async def _write_phi_block_audit(
    inp: PreToolUseInput, matches: list[PhiMatch], session: AsyncSession
) -> None:
    """Write one audit_events row (event_type='phi_block') for a blocked send.

    Mirrors post_tool_use's clear-text-payload discipline: payload_encrypted holds
    clear-text JSON bytes + a SHA-256 hash with key_version=0 until Phase 4 swaps
    in AES-GCM via Key Vault. NEVER stores the email body (which is the suspected
    PHI) — only the detected pattern types/snippets + a 50-char subject preview.
    """
    subject = inp.tool_args.get("subject", "") or ""
    payload = {
        "tool": "send_email",
        "actor": inp.actor,
        "matches": [m.to_dict() for m in matches],
        "subject_preview": subject[:50],
        "template_id": inp.tool_args.get("template_id"),
    }
    payload_bytes = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    payload_hash = hashlib.sha256(payload_bytes).digest()

    try:
        case_uuid: uuid.UUID | None = uuid.UUID(str(inp.case_file_id)) if inp.case_file_id else None
    except (ValueError, AttributeError, TypeError):
        case_uuid = None

    event = AuditEvent(
        event_type="phi_block",
        actor=inp.actor,
        case_file_id=case_uuid,
        # TODO(Phase 4): AES-GCM via Key Vault; clear-text JSON bytes for now.
        payload_encrypted=payload_bytes,
        payload_hash=payload_hash,
        key_version=0,
        tools_invoked=["send_email"],
        outcome="blocked",
        error_details=f"send_email PHI block: {len(matches)} pattern matches",
    )
    session.add(event)
    await session.flush()  # surface write failures to the caller; caller commits
