"""Lead Planner (V1-Lite collapsed) — composes the user-facing answer.

In V1-Lite, the Lead Planner's role at audit-complete time is:
  1. Run the enumerated 7-question thinking loop (Change Order 001 item 2 —
     the loop is in behavioral_core; the explicit reinforcement helps the
     model honor it under length pressure).
  2. Read the case state + findings (already written by Bill Detective +
     Math Person).
  3. Compose the final response: Tier A facts (the three numbers + key
     figures) → Tier B legal/coverage claims (cited) → Tier C scripted
     next-action recommendation.
  4. Surface anticipated next steps (P2 — never end without 'what's next').
  5. Avoid options dumping (P5) — recommend ONE path, note alternatives in
     prose if relevant.

In V1-Lite Lead Planner does NOT draft letters (the Document Generation
Skill is deferred) — recommendations are SCRIPTED phone calls / scripted
letters the user makes themselves.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_loader import compose_chat_system_prompt, compose_system_prompt
from app.agents.runner import RunResult, run_agent
from app.config import get_settings

log = structlog.get_logger(__name__)


TOOL_ALLOWLIST = [
    "pg_case_file_get",
    "pg_upsert_finding",
    "pg_deadline_upsert",
    "pg_list_due",
    "qdrant_search_billing_codes",
    "qdrant_search_error_detection_rules",
    "qdrant_search_laws_regulations",
    "qdrant_search_payer_policies",
    "cost_estimate_medicare_rvu",
    "upload_extract_coverage",
    "upload_extract_eob",
    "bill_ocr_extract",
    "deadline_calculate",
    "notify_user",
    "legal_doi_complaint_route",
]


def _build_user_message(
    case_file_id: str,
    bill_detective_summary: str,
    math_person_summary: str,
) -> str:
    return (
        f"You are the V1-Lite Lead Planner. Compose the final user-facing response for case file "
        f"`{case_file_id}`.\n\n"
        "Bill Detective just ran. Their summary:\n"
        "---\n"
        f"{bill_detective_summary or '(no summary returned)'}\n"
        "---\n\n"
        "Math Person just ran. Their summary:\n"
        "---\n"
        f"{math_person_summary or '(no summary returned)'}\n"
        "---\n\n"
        "Their structured findings are persisted in the case file — call pg_case_file_get to read "
        "current state, and you may issue additional retrievals if needed to back a citation.\n\n"
        "Run the enumerated seven-question thinking loop INTERNALLY, then output the user-facing "
        "markdown answer:\n"
        "  1. Lead with the three numbers (Tier A) — billed / EOB-claimed / Tyndale-computed.\n"
        "  2. State the gap side and category in plain English (Tier A facts + Tier B claim with "
        "an inline citation in [authority §section, src_id] format if you have a retrieved source; "
        "omit the legal claim if you cannot ground it).\n"
        "  3. Recommend ONE next action (Tier C). In V1-Lite that means a SCRIPTED phone call or "
        "letter the user makes — Tyndale does not draft and send.\n"
        "  4. Surface 'Anticipated next steps' — at least one specific item the user should expect "
        "to do or hear about next, with a deadline if applicable.\n\n"
        "End with the permanent footer: 'Tyndale provides medical billing and coverage advocacy, "
        "not medical, legal, or financial advice.'"
    )


async def compose_final(
    case_file_id: str,
    bill_detective_summary: str,
    math_person_summary: str,
    *,
    session: AsyncSession | None = None,
) -> RunResult:
    settings = get_settings()
    system_blocks = compose_system_prompt(
        "lead_planner_v1_lite",
        include_skills=None,
    )
    return await run_agent(
        model=settings.claude_model_for("lead_planner"),
        system_blocks=system_blocks,
        tool_names=TOOL_ALLOWLIST,
        initial_user_message=_build_user_message(
            case_file_id, bill_detective_summary, math_person_summary
        ),
        case_file_id=case_file_id,
        actor="lead_planner",
        session=session,
    )


# ---------------------------------------------------------------------------
# Chat mode (Phase CO-10)
#
# A chat turn is the Lead Planner posture run conversationally. The ONLY branch
# is mode selection: `per_case` (case-aware, full analysis posture) vs `freeform`
# (knowledge-base posture, no specific-case analysis, redirect-to-case on a
# specific situation). The mode picks the system prompt; the streaming loop +
# tool allowlist live in `app/agents/chat.py`.
# ---------------------------------------------------------------------------


def chat_mode_for_case(case_id) -> str:
    """`per_case` when a case file is attached, else `freeform`."""
    return "freeform" if case_id is None else "per_case"


def chat_system_blocks(chat_mode: str) -> list[dict]:
    """Select the chat system prompt for a mode (`per_case` | `freeform`)."""
    return compose_chat_system_prompt(chat_mode)
