"""Claude Agent SDK hook stubs (Phase 1C).

All five surfaces return safe defaults and are clearly marked as stubs. The
security/HIPAA contact replaces these in Phase 4. See docs/integration-contracts.md.
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
    """Emit a startup warning that the hook layer is stubbed (not security-wired)."""
    log.warning(
        "hooks.stub_active",
        message="STUB — security spine not yet wired (Phase 4)",
        hooks=[
            "user_prompt_submit",
            "pre_tool_use",
            "post_tool_use",
            "stop",
            "crisis_classifier",
        ],
    )


__all__ = [
    "log_stub_warnings",
    "user_prompt_submit_hook",
    "pre_tool_use_hook",
    "post_tool_use_hook",
    "stop_hook",
    "crisis_classifier",
]
