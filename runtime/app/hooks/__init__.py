"""Claude Agent SDK hook surfaces.

Most are now real: PostToolUse (audit row + AES-GCM encryption), Stop (citation ship-gate),
the crisis classifier (DL-04), and PreToolUse's invariants (date-filter, approval-token,
send_email PHI guard, case-file tenant binding). The remaining true stubs are the
Presidio-based scrubs — PreToolUse arg-scrubbing and the UserPromptSubmit injection scrub —
owned by the security/HIPAA contact (DL-11, Phase 4). See docs/integration-contracts.md.
``log_stub_warnings`` reports each surface's real/partial/stub status at startup.
"""

from __future__ import annotations

import structlog

from app.hooks.crisis_classifier import crisis_classifier
from app.hooks.post_tool_use import post_tool_use_hook
from app.hooks.pre_tool_use import pre_tool_use_hook
from app.hooks.stop import stop_hook
from app.hooks.user_prompt_submit import user_prompt_submit_hook

log = structlog.get_logger(__name__)


def log_stub_warnings() -> None:
    """Log the ACTUAL wiring status of each hook surface at startup, so the remaining true
    stubs are visible and the real hooks don't cry wolf (Phase 2.6). Wired surfaces log at
    info; the partial + stub surfaces (the Presidio-based scrubs — DL-11) log at warning."""
    for hook, detail in (
        ("post_tool_use", "audit_events row + AES-GCM payload encryption"),
        ("stop", "citation ship-gate (regenerate <=3 then human_review)"),
        ("crisis_classifier", "Haiku layer + deterministic keyword screen (DL-04)"),
    ):
        log.info("hooks.surface", hook=hook, status="wired", detail=detail)

    log.warning(
        "hooks.surface",
        hook="pre_tool_use",
        status="partial",
        detail=(
            "real gates (date-filter, approval-token, send_email PHI guard, case-file tenant "
            "binding); Presidio arg-scrub still a stub (DL-11 / Phase 4)"
        ),
    )
    log.warning(
        "hooks.surface",
        hook="user_prompt_submit",
        status="stub",
        detail="prompt-injection scrub is a pass-through — DL-11 / Phase 4 security contractor",
    )


__all__ = [
    "log_stub_warnings",
    "user_prompt_submit_hook",
    "pre_tool_use_hook",
    "post_tool_use_hook",
    "stop_hook",
    "crisis_classifier",
]
