"""Bill Detective subagent — provider-side and encounter-mismatch findings.

Loads ``bill_error_detection`` Skill (SKILL.md + 00_diagnostic_index.md only;
deeper category files surface via subsequent tool calls per the two-layer
Skill architecture).

V1-Lite scope: surface findings via ``pg_upsert_finding`` with
``finding_type=provider_side`` or ``encounter_mismatch``. Returns a minimal
summary back to the orchestrator. The MRI walking-skeleton scenario expects
zero provider-side findings here (the error is payer-side, found by Math
Person); BD's run still happens because effort scaling for "bill check with
finding" is fixed at 2 subagents per V1-Lite collapsed Lead Planner doctrine.
"""

from __future__ import annotations

import structlog

from app.agents.context_loader import compose_system_prompt
from app.agents.runner import RunResult, run_agent
from app.config import get_settings

log = structlog.get_logger(__name__)


TOOL_ALLOWLIST = [
    "bill_ocr_extract",
    "upload_extract_eob",
    "qdrant_search_billing_codes",
    "qdrant_search_error_detection_rules",
    "qdrant_search_payer_policies",
    "ncci_check_pair",
    "mue_check",
    "pg_case_file_get",
    "pg_upsert_finding",
]


def _build_user_message(case_file_id: str) -> str:
    return (
        f"You are Bill Detective. Audit case file `{case_file_id}` for provider-side errors "
        "(upcoding, unbundling, duplicate charges, phantom charges) and encounter-mismatch issues "
        "(line items that don't match what actually happened).\n\n"
        "1. Read the case file with pg_case_file_get to see its current state and uploaded "
        "documents.\n"
        "2. For any uploaded bill/EOB, run bill_ocr_extract or upload_extract_eob.\n"
        "3. Walk the 23-check diagnostic index — query Qdrant for each plausible category, then "
        "drill into the specific check.\n"
        "4. For each finding you confirm, call pg_upsert_finding with:\n"
        "   - finding_type: 'provider_side' or 'encounter_mismatch'\n"
        "   - category: the specific check name (e.g. 'upcoding_em_visit')\n"
        "   - voice_tier: 'A' for code-level facts, 'B' for legal claims (with citation), "
        "'C' for recommendations\n"
        "   - facts: precise dollar amounts / CPT codes / dates from the document\n"
        "   - citations: only when you have a real retrieved source\n"
        "5. When you are done, output a 2-3 sentence summary of what you found. "
        "If you found nothing, say so explicitly — that itself is a useful finding."
    )


async def run(case_file_id: str) -> RunResult:
    settings = get_settings()
    system_blocks = compose_system_prompt(
        "bill_detective",
        include_skills=["bill_error_detection"],
    )
    return await run_agent(
        model=settings.claude_model_for("bill_detective"),
        system_blocks=system_blocks,
        tool_names=TOOL_ALLOWLIST,
        initial_user_message=_build_user_message(case_file_id),
    )
