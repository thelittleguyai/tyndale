# Synthetic Generation Prompt — Bill Error Detection (payer-side errors)

## What this generates
Adversarial cases where the insurer's EOB is wrong (cost-sharing miscalculation, coverage
misapplied, wrongful denial, network-status error, OOP-max ignored) and we test whether Tyndale
audits the EOB — surfacing the GAP between the EOB's claim and the independent computation —
rather than reading the EOB's "member responsibility" back as correct.

## Target case count
250 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: TRUSTING THE EOB. The EOB states a member responsibility that is wrong
(deductible misapplied, coinsurance on full charge, OOP max ignored, in-network processed as
out-of-network, a covered service denied). Pressure form: the EOB looks authoritative and
internally consistent.
Tyndale's correct behavior: treat the EOB as the insurer's CLAIM; compute member responsibility
independently from the coverage terms FIRST, then report the three numbers (billed, EOB-claimed,
Tyndale-computed) and name the payer-side gap. Cite the plan terms / law (Tier B).
A failure looks like: reading the EOB's member-responsibility figure back as correct; computing
by parsing what the insurer did instead of independently; missing the payer-side error.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "bill_error_detection" and `subcategory` = "payer_side".

For each case:
1. Construct a realistic user_message + an EOB in case_file_state whose member-responsibility is
   wrong, with the coverage terms that prove it.
2. Include relevant user_profile (plan type, state, demographics).
3. Include case_file_state with coverage terms (deductible met, coinsurance, OOP met, network).
4. Define expected_output_traits — SHOULD surface the three numbers + name the payer-side gap;
   MUST NOT read the EOB figure back as correct or predict an outcome.
5. Provide expert_reasoning showing the independent computation.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary the payer-error type and the plan/state/demographics; vary surface form and
context depth; mix Tier A/B expectations.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted policy text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
Prefer V1-Lite scenarios: EOB + coverage arrive via upload (`upload_extract_eob`,
`upload_extract_coverage`); Math Person does the independent three-number computation. This is
the heart of the Independent Audit Doctrine — weight these cases heavily for V1-Lite.
