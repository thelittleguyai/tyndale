"""Lead-with-status greeting composition (Change Order 001 item 3).

When the user opens the app and they have open case files, the hero
greeting on the dashboard is composed by Claude (V1-Lite Lead Planner)
from the current case state. Falls back to a programmatic concatenation
when USE_REAL_CLAUDE is off or no Anthropic key is configured.

The greeting is a one-paragraph status-forward summary — leads with where
things stand, names the next concrete thing the user should expect (P2).
"""

from __future__ import annotations

import json

import structlog

from app.agents.orchestrator import _has_real_anthropic_creds
from app.config import get_settings

log = structlog.get_logger(__name__)


def _programmatic_fallback(open_cases: list[dict]) -> str:
    """Plain-text greeting that needs no model. Reads naturally enough for
    walking-skeleton use; Claude takes over when creds are configured."""
    n = len(open_cases)
    if n == 1:
        c = open_cases[0]
        deadline = (
            f" — next deadline {c['next_deadline_date']} ({c['next_deadline_label']})"
            if c.get("next_deadline_date")
            else ""
        )
        return (
            f"Here's where your 1 open issue stands: "
            f"{c['headline']} (open {c['days_open']} days{deadline})."
        )
    bits = []
    for c in open_cases[:3]:
        bits.append(f"{c['headline']} ({c['days_open']}d)")
    more = f", plus {n - 3} more" if n > 3 else ""
    return f"Here's where your {n} open issues stand: " + "; ".join(bits) + more + "."


async def compose_status_greeting(open_cases: list[dict]) -> str | None:
    """Returns the status-forward greeting, or None if no open cases."""
    if not open_cases:
        return None

    settings = get_settings()
    if not settings.use_real_claude or not _has_real_anthropic_creds(settings):
        return _programmatic_fallback(open_cases)

    # Real Claude path. Keep it short + cheap.
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.claude_model_for("lead_planner"),
            max_tokens=300,
            system=(
                "You are Tyndale's V1-Lite Lead Planner composing the session-open "
                "greeting for the dashboard (Change Order 001 item 3). Lead with "
                "status: where the user's open issues stand, most urgent first, "
                "and name the next concrete thing they should expect. ONE short "
                "paragraph, plain text, no bullet points, no model speculation, "
                "no medical/legal/financial advice."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Compose the session-open greeting from this open-case "
                        "snapshot:\n\n" + json.dumps(open_cases, default=str, indent=2)
                    ),
                }
            ],
        )
        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        text = "\n".join(text_blocks).strip()
        if not text:
            return _programmatic_fallback(open_cases)
        return text
    except Exception as exc:  # noqa: BLE001 — fall back cleanly
        log.warning("greeting.claude_call_failed_falling_back", error=str(exc))
        return _programmatic_fallback(open_cases)
