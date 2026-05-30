"""Bill Detective subagent — two modes (Phase 2I).

- mode='translate' (encounter-verification pass): translate each charged line
  item to plain language the user can confirm against their lived experience.
  Loads SKILL.md + the 06_encounter_verification reference files. Persists each
  line item via pg_store_line_item. NO findings written here.
- mode='diagnose' (default; the original behavior): walk the 23-check
  diagnostic with the user's confirmations as ground-truth input. Mismatches
  drive the upcoding / phantom_charges reference loads. Writes findings via
  pg_upsert_finding.

HARD LINE (refusals.md + L07): in translate mode the agent asks the user to
confirm FACTS about the visit ("Were you in the ER a long time?"), NEVER a
clinical judgment ("Was this necessary?"). The pg_store_line_item tool
description enforces this in its contract text.
"""

from __future__ import annotations

import json

import structlog

from app.agents.context_loader import compose_system_prompt
from app.agents.runner import RunResult, run_agent
from app.config import get_settings

log = structlog.get_logger(__name__)


# Diagnose mode — full provider-side + encounter-mismatch diagnostic.
DIAGNOSE_TOOLS = [
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

# Translate mode — OCR + persist plain-language line items. No findings.
TRANSLATE_TOOLS = [
    "bill_ocr_extract",
    "upload_extract_eob",
    "qdrant_search_billing_codes",
    "pg_case_file_get",
    "pg_store_line_item",
]


def _translate_message(case_file_id: str) -> str:
    return (
        f"You are Bill Detective in ENCOUNTER-VERIFICATION (translate) mode for case "
        f"`{case_file_id}`. Do NOT diagnose errors yet — your only job is to translate each "
        "charged line item into plain language the user can confirm against what actually "
        "happened at their visit.\n\n"
        "Consult bill_error_detection/06_encounter_verification/lineitem_plain_language.md for "
        "the translation approach.\n\n"
        "1. pg_case_file_get to read the case + its uploaded documents.\n"
        "2. bill_ocr_extract (and upload_extract_eob if an EOB is present) to get the line items.\n"
        "3. For EACH charged line item, call pg_store_line_item with:\n"
        "   - code, code_system, raw_description (verbatim from the bill)\n"
        "   - plain_language_translation: what the code MEANS in plain English, framed as a FACT "
        "about what happened ('A high-complexity emergency room visit' / 'A lab test for X'). \n"
        "   - plain_language_context: optional non-leading context ('ER visits coded at this level "
        "usually involve a long stay or a complex situation') — informational, never a clinical "
        "judgment about necessity.\n"
        "   - high_risk: true for E/M visit levels, time-based codes, and other upcoding/phantom-"
        "prone codes; false for routine items.\n"
        "   - example_scenarios: 3-5 short, factual, SECOND-PERSON PAST-TENSE scenarios of what a "
        "typical patient would have experienced for this category of service ('You'd typically have "
        "spent 1-2 hours in the ER', 'You'd have had blood drawn from your arm'). See the Skill's "
        "'Example scenarios per category' section for per-category guidance. These help the user "
        "recall what happened — same hard line: what HAPPENED, never whether it should have.\n"
        "   - billed_amount, units when present.\n\n"
        "ABSOLUTE RULE (refusals.md): translate to a FACT the user can verify from their lived "
        "experience ('Were you actually in the ER for hours?'), NEVER a clinical judgment "
        "('Was this medically necessary?' / 'Should you have gotten this?'). The user verifies "
        "WHAT HAPPENED, not whether it should have happened.\n\n"
        "When every line item is stored, output a one-sentence confirmation of how many line "
        "items you translated."
    )


def _diagnose_message(case_file_id: str, confirmations: list[dict] | None) -> str:
    base = (
        f"You are Bill Detective in DIAGNOSE mode for case `{case_file_id}`. Audit for "
        "provider-side errors (upcoding, unbundling, duplicate charges, phantom charges) and "
        "encounter-mismatch issues.\n\n"
        "1. pg_case_file_get to read case state, documents, and the stored line items.\n"
        "2. bill_ocr_extract / upload_extract_eob as needed.\n"
        "3. Walk the 23-check diagnostic — SKIP encounter-verification checks 0a/0b (already done "
        "in the translate pass). Query Qdrant per plausible category, then drill into the check.\n"
    )
    if confirmations:
        base += (
            "\nThe user has CONFIRMED these line items (ground-truth input — treat as fact):\n"
            "---\n" + json.dumps(confirmations, indent=2, default=str) + "\n---\n"
            "For any line item the user answered 'no' (didn't happen) or 'not_sure' on a high-risk "
            "item, pursue it as a candidate finding: route through upcoding.md (if a visit-level / "
            "time-based code) or phantom_charges.md (if a service/test the user says they never "
            "received). Confirm against the rules before writing the finding.\n"
        )
    base += (
        "\n4. For each finding you confirm, call pg_upsert_finding with finding_type "
        "('provider_side' | 'encounter_mismatch'), category, voice_tier, precise facts, and "
        "citations only when you have a retrieved source.\n"
        "5. Output a 2-3 sentence summary. If nothing, say so explicitly."
    )
    return base


async def run(
    case_file_id: str,
    *,
    mode: str = "diagnose",
    confirmations: list[dict] | None = None,
) -> RunResult:
    settings = get_settings()
    system_blocks = compose_system_prompt(
        "bill_detective",
        include_skills=["bill_error_detection"],
    )
    if mode == "translate":
        tool_names = TRANSLATE_TOOLS
        message = _translate_message(case_file_id)
    else:
        tool_names = DIAGNOSE_TOOLS
        message = _diagnose_message(case_file_id, confirmations)
    return await run_agent(
        model=settings.claude_model_for("bill_detective"),
        system_blocks=system_blocks,
        tool_names=tool_names,
        initial_user_message=message,
    )
