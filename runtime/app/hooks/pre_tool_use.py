"""PreToolUse hook — STUB (Phase 1C).

Presidio PHI scrubbing lands in Phase 4. This stub enforces the two
non-scrubbing rules from the contract so they hold even pre-Presidio:
  1. Effective-date filter required on the date-filtered Qdrant searches.
  2. Approval token required for gated tools (send_email, doc_generate).
"""

from __future__ import annotations

from app.hooks.contracts import PreToolUseInput, PreToolUseResult

DATE_FILTERED_TOOLS = {"qdrant_search_laws_regulations", "qdrant_search_payer_policies"}
GATED_TOOLS = {"send_email", "doc_generate"}


def pre_tool_use_hook(inp: PreToolUseInput) -> PreToolUseResult:
    # Rule 3 (contract): point-in-time filter is mandatory on these searches.
    if inp.tool_name in DATE_FILTERED_TOOLS and not inp.tool_args.get("effective_date"):
        return PreToolUseResult(
            sanitized_args=inp.tool_args,
            approved=False,
            block_reason=f"{inp.tool_name} requires an 'effective_date' filter (point-in-time rule)",
        )

    # Rule 2 (contract): gated tools require a user-approval token.
    if inp.tool_name in GATED_TOOLS and not inp.tool_args.get("approval_token"):
        return PreToolUseResult(
            sanitized_args=inp.tool_args,
            approved=False,
            block_reason=f"{inp.tool_name} requires an 'approval_token' (user-approval gate)",
        )

    # STUB: Rule 1 (Presidio scrubbing) is a no-op until Phase 4.
    return PreToolUseResult(sanitized_args=inp.tool_args, approved=True, block_reason=None)
