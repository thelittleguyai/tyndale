"""Dashboard welcome-summary composition (Change Order 001 item 3; guardrails 2026-07-15).

A one-to-two-sentence, status-forward line for the dashboard, composed from the user's current case
states. The browser review caught the model fabricating a human review loop ("expect the next
update from our review team", "a reviewer will pick up where things left off") — THERE ARE NO
HUMANS IN THIS LOOP. Three guardrails:

1. Constrain — the generator prompt (D1: record_welcome_summary_instructions) forbids human actors,
   invented process steps, and promises about who does what next; facts only, user-actionable, ≤2
   sentences.
2. Validate — `passes_guardrails` rejects any output matching a banned pattern (reviewer / review
   team / our team / staff / agent will / specialist / processing queue …); a rejection (or an
   empty / failed / timed-out generation) falls back to the deterministic template.
3. Deterministic fallback — composed purely from case-state counts (D1:
   record_welcome_summary_fallback), so it can never invent anything.

The generator's framing and the fallback template are D1 orchestration-script keys, so Brock's
writers own the final voice and the staging placeholder gate covers them. Caching (regenerate only
when the case-state hash changes) lives at the call site (dashboard).
"""

from __future__ import annotations

import re

import structlog

from app.agents.context_loader import orchestration_step
from app.agents.orchestrator import _has_real_anthropic_creds
from app.agents.runner import _client
from app.config import get_settings

log = structlog.get_logger(__name__)

# Outputs containing any of these are rejected (case-insensitive). Extensible — add a phrase here
# and it's covered by the validator + its test. There are no humans in the loop, and the summary
# never promises a process step or who acts next.
BANNED_PATTERNS: tuple[str, ...] = (
    r"review team",
    r"reviewer",
    r"our team",
    r"\bstaff\b",
    r"\bagent will\b",
    r"specialist",
    r"processing queue",
    r"a (?:person|human) will",
    r"our reviewers?",
    r"pick(?:ed)? up where",
    r"resume processing",
)
_BANNED_RE = re.compile("|".join(BANNED_PATTERNS), re.IGNORECASE)


def passes_guardrails(text: str) -> bool:
    """True if the generated summary is safe to show: non-empty and free of any banned pattern."""
    return bool(text and text.strip()) and _BANNED_RE.search(text) is None


# status -> the plain-language category the deterministic summary counts by. Statuses not mapped
# here (open / in_progress / audit_running / encounter_*) are "in progress".
_CATEGORY: dict[str, str] = {
    "audit_incomplete": "needs_documents",
    "awaiting_eob_confirmation": "needs_documents",
    "audit_complete": "results",
    "resolved": "resolved",
    "extraction_failed": "unreadable",
}
# Terminal/junk states that don't count toward the dashboard summary at all.
_IGNORED = {"not_a_bill", "archived"}


def _category(status: str) -> str | None:
    if status in _IGNORED:
        return None
    return _CATEGORY.get(status, "in_progress")


def _deterministic_summary(case_states: list[dict]) -> str | None:
    """Compose the fallback purely from case-state counts — no model, nothing invented. Returns
    None when there are no cases worth summarizing (the dashboard then shows no status line)."""
    cats: dict[str, int] = {}
    for s in case_states:
        c = _category(str(s.get("status", "")))
        if c:
            cats[c] = cats.get(c, 0) + 1
    total = sum(cats.values())
    if total == 0:
        return None
    # Order the breakdown by user urgency; each is a plain factual noun phrase.
    phrasing = [
        ("needs_documents", "need documents"),
        ("unreadable", "to re-upload"),
        ("in_progress", "in progress"),
        ("results", "with results ready"),
        ("resolved", "resolved"),
    ]
    parts = [f"{cats[k]} {label}" for k, label in phrasing if cats.get(k)]
    breakdown = ", ".join(parts)
    return orchestration_step("record_welcome_summary_fallback", total=total, breakdown=breakdown)


async def compose_status_greeting(case_states: list[dict]) -> str | None:
    """The dashboard welcome summary from the current case states, or None if nothing to summarize.

    case_states: [{status, next_deadline_date?, next_deadline_label?}, …]. Tries the constrained
    generator, validates it, and falls back to the deterministic template on rejection / no-creds /
    empty / error."""
    fallback = _deterministic_summary(case_states)
    if fallback is None:
        return None

    settings = get_settings()
    if not settings.use_real_claude or not _has_real_anthropic_creds(settings):
        return fallback

    try:
        client = _client()
        response = await client.messages.create(
            model=settings.claude_model_for("lead_planner"),
            max_tokens=160,
            system=orchestration_step("record_welcome_summary_instructions"),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Case states (facts only; do not invent anything beyond these):\n"
                        + "\n".join(
                            f"- status={s.get('status')}"
                            + (
                                f", deadline={s.get('next_deadline_label')} {s.get('next_deadline_date')}"
                                if s.get("next_deadline_date")
                                else ""
                            )
                            for s in case_states
                        )
                    ),
                }
            ],
        )
        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        text = "\n".join(text_blocks).strip()
        if passes_guardrails(text):
            return text
        log.warning("greeting.rejected_falling_back", reason="banned_pattern_or_empty")
        return fallback
    except Exception as exc:  # noqa: BLE001 — never fail the dashboard; fall back cleanly
        log.warning("greeting.claude_call_failed_falling_back", error=str(exc))
        return fallback
