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

import json

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_loader import compose_system_prompt
from app.agents.runner import RunResult, run_agent
from app.config import get_settings

log = structlog.get_logger(__name__)


TOOL_ALLOWLIST = [
    "upload_extract_coverage",
    "upload_extract_eob",
    "qdrant_search_payer_policies",
    "cost_estimate_fair_health",  # deferred (Phase 2G) — Math Person uses RVU instead
    "cost_estimate_medicare_rvu",
    "pg_case_file_get",
    "pg_upsert_finding",
]


def _build_user_message(case_file_id: str, accumulator: dict | None = None) -> str:
    base = (
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
    if accumulator:
        # CO-12B: the orchestrator ran the deterministic accumulator engine +
        # three-way cross-validation (DL-72) before this agent. The computed
        # reconstruction is AUTHORITATIVE — the EOB's stated YTD is never adopted.
        base += (
            "\n\nPRE-COMPUTED ACCUMULATOR (Tyndale's deterministic reconstruction from the "
            "uploaded EOBs — authoritative per DL-72; treat as ground truth over any "
            "EOB-stated year-to-date figure):\n"
            "---\n" + json.dumps(accumulator, indent=2, default=str) + "\n---\n"
            "Use deductible_applied / oop_applied above as the deductible-met / OOP-met basis "
            "in STEP 2 instead of re-deriving them or trusting the EOB's stated YTD. Heed the "
            "recorded assumptions and confidence — surface them explicitly when they "
            "materially qualify your answer. If these figures disagree with the EOB's stated "
            "numbers, an accumulator_discrepancy finding has ALREADY been written for this "
            "case — do NOT write a duplicate; factor the discrepancy into your gap analysis "
            "and summary instead."
        )
    return base


async def run(
    case_file_id: str,
    *,
    accumulator: dict | None = None,
    session: AsyncSession | None = None,
) -> RunResult:
    settings = get_settings()
    system_blocks = compose_system_prompt(
        "math_person",
        include_skills=["coverage_connection_fhir", "cost_estimation"],
    )
    return await run_agent(
        model=settings.claude_model_for("math_person"),
        system_blocks=system_blocks,
        tool_names=TOOL_ALLOWLIST,
        initial_user_message=_build_user_message(case_file_id, accumulator),
        case_file_id=case_file_id,
        actor="math_person",
        session=session,
    )
