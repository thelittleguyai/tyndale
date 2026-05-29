"""Math Person subagent — independent three-number audit.

Loads ``coverage_connection_fhir`` Skill (V1-Lite uses the upload tools that
match the FHIR tools' return shapes) and ``cost_estimation`` Skill.

V1-Lite scope: compute the member responsibility INDEPENDENTLY from the
coverage terms FIRST, then compare to the billed amount and the EOB's claimed
member responsibility. Surface the three-number audit + the gap side (payer-
side vs provider-side) via ``pg_upsert_finding`` with
``finding_type=payer_side`` (when the gap is the payer's) or
``provider_side`` (when the bill itself is off).

The MRI walking-skeleton scenario expects one payer-side finding with
billed=$1200, EOB=$1200, Tyndale=$560 (gap = $640 payer-side cost-sharing
miscalculation).
"""

from __future__ import annotations

import structlog

from app.agents.context_loader import compose_system_prompt
from app.agents.runner import RunResult, run_agent
from app.config import get_settings

log = structlog.get_logger(__name__)


TOOL_ALLOWLIST = [
    "upload_extract_coverage",
    "upload_extract_eob",
    "qdrant_search_payer_policies",
    "cost_estimate_fair_health",   # deferred (Phase 2G) — Math Person uses RVU instead
    "cost_estimate_medicare_rvu",
    "pg_case_file_get",
    "pg_upsert_finding",
]


def _build_user_message(case_file_id: str) -> str:
    return (
        f"You are Math Person. Run the independent three-number audit on case file `{case_file_id}`.\n\n"
        "STEP 1 — load the case file (pg_case_file_get) and any uploaded coverage / EOB documents "
        "(upload_extract_coverage / upload_extract_eob).\n\n"
        "STEP 2 — compute what the member SHOULD owe (tyndale_computed_responsibility) using the "
        "actual coverage terms (deductible_amount, deductible_met, coinsurance_percent, "
        "oop_max_amount, oop_max_met, network_tier). Do this BEFORE looking at the EOB's claimed "
        "member responsibility — the EOB does not anchor the result. If a coverage term is missing "
        "or low-confidence, surface that explicitly.\n\n"
        "STEP 3 — gather the other two numbers: billed_amount (from the bill / OCR) and "
        "eob_stated_responsibility (from the EOB).\n\n"
        "STEP 4 — name the gap. If your independent figure is below the EOB's claimed amount, the "
        "gap is payer-side cost-sharing miscalculation. If above the billed amount, look for a "
        "provider-side overcharge. If your independent figure matches both, no gap — report that.\n\n"
        "STEP 5 — write a finding via pg_upsert_finding. facts MUST include "
        "{provider_billed, eob_member_responsibility, tyndale_computed, gap}. voice_tier 'B' for "
        "the claim ('appears to violate' / 'is entitled to'), with a citation [authority §section, "
        "src_id] from a retrieved source. If you cannot retrieve a source, OMIT the legal claim "
        "rather than fabricate.\n\n"
        "STEP 6 — output a 2-3 sentence summary of the three numbers and the gap side."
    )


async def run(case_file_id: str) -> RunResult:
    settings = get_settings()
    system_blocks = compose_system_prompt(
        "math_person",
        include_skills=["coverage_connection_fhir", "cost_estimation"],
    )
    return await run_agent(
        model=settings.claude_model_for("math_person"),
        system_blocks=system_blocks,
        tool_names=TOOL_ALLOWLIST,
        initial_user_message=_build_user_message(case_file_id),
    )
