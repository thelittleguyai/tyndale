"""Auto-generate a short conversation title from the first user message (CO-10).

Uses Anthropic **Haiku** for cost efficiency when real Claude is enabled;
otherwise a deterministic stub (first words of the message) so tests + local dev
work without creds. Per **DL-47**, the generated title is PHI-scanned before it's
allowed to become a (conversation-list-visible) title — any PHI signal collapses
it to "Untitled conversation". This reuses the exact `detect_phi` hook that
guards `send_email`.
"""

from __future__ import annotations

import structlog

from app.agents.runner import _client, real_claude_enabled
from app.auth.phi_patterns import detect_phi
from app.config import get_settings

log = structlog.get_logger(__name__)

_FALLBACK = "Untitled conversation"
_MAX_LEN = 80
_SYSTEM = (
    "Generate a 3-7 word title for a medical-billing help chat, summarizing the "
    "user's first message. Reply with ONLY the title — no quotes, no trailing "
    "punctuation. Never include names, dollar amounts, dates of birth, or any "
    "personal identifier."
)


def _stub_title(msg: str) -> str:
    words = msg.strip().split()
    return " ".join(words[:6]) if words else _FALLBACK


async def _haiku_title(msg: str) -> str:
    settings = get_settings()
    client = _client()
    resp = await client.messages.create(
        model=settings.resolved_model(settings.claude_default_model_haiku),
        max_tokens=24,
        system=[{"type": "text", "text": _SYSTEM}],
        messages=[{"role": "user", "content": f"First user message:\n\n{msg}\n\nTitle:"}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return " ".join(parts).strip()


async def auto_generate_title(first_user_message: str) -> str:
    """Return a 3-7 word title. Falls back to "Untitled conversation" on any
    failure OR when the candidate trips the PHI guard (DL-47)."""
    try:
        raw = (
            await _haiku_title(first_user_message)
            if real_claude_enabled()
            else _stub_title(first_user_message)
        )
    except Exception as exc:  # noqa: BLE001 — title gen is best-effort, never fatal
        log.warning("conversation_title.generate_failed", error=str(exc))
        return _FALLBACK

    raw = (raw or "").strip().strip('"').strip()
    if not raw:
        return _FALLBACK
    # DL-47: titles are visible in lists — never let a PHI signal through.
    if detect_phi(raw):
        log.info("conversation_title.phi_blocked")
        return _FALLBACK
    return raw[:_MAX_LEN]
