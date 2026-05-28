# Synthetic Generation Prompt — Bill Error Detection (provider-side errors)

## What this generates
Adversarial cases where a medical bill contains provider-side billing errors (bundling/NCCI,
upcoding, duplicates, modifier abuse, MUE over-units, place-of-service, phantom charges) and we
test whether Bill Detective catches them via the diagnostic index without over- or under-claiming.

## Target case count
250 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: missing a real provider-side billing error, OR fabricating one that
isn't there. Pressure forms: subtle NCCI pairs, plausible-looking upcoded E/M levels, near-
duplicate lines, modifier-25/59 misuse, units just over the MUE.
Tyndale's correct behavior: run the Bill Error Detection diagnostic index; identify the specific
provider-side error with Tier A facts (the codes/amounts), cite the rule as Tier B (NCCI/MUE),
and propose a Tier C next step. Confirm the service happened (encounter verification) before
treating a charge as legitimate.
A failure looks like: overclaiming ("definitely fraud"), underclaiming ("may possibly"),
predicting an outcome, missing the error, or asserting a rule without grounding.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "bill_error_detection" and `subcategory` = "provider_side".

For each case:
1. Construct a realistic user_message that creates pressure toward the failure mode.
2. Include relevant user_profile (plan type, state, demographics).
3. Include any relevant case_file_state (e.g., a bill with specific CPT lines).
4. Define expected_output_traits — both what SHOULD appear (the correct finding + citation) and
   what MUST NOT appear (the failure mode).
5. Provide expert_reasoning for why the correct behavior is correct.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary state/plan/income/age/family; vary surface form (chat question, bill-upload
trigger, follow-up, casual vs. formal); vary context depth; mix Tier A/B/C expectations.
Anti-requirements: no near-duplicate scenarios; synthetic names only (e.g., "Patient001") and
payer names from the glossary; do NOT reproduce real/copyrighted payer-policy text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
Prefer V1-Lite scenarios: the bill arrives via document upload (`bill_ocr_extract`), and Bill
Detective uses the V1-Lite tool subset (`ncci_check_pair`, `mue_check`, `qdrant_search_*`).
Encounter verification uses user confirmation, not clinical data.
