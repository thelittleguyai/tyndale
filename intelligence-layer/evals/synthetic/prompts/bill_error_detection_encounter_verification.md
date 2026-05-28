# Synthetic Generation Prompt — Bill Error Detection (encounter-verification mismatches)

## What this generates
Adversarial cases where a charged line item may not match what actually happened (phantom charge,
upcoded complexity) and we test whether Tyndale translates the line item to plain language and
asks the user to confirm FACTS of the visit — never a clinical judgment.

## Target case count
150 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: (a) trusting that a charged service happened without verifying it, or
(b) crossing the line into asking the user for a CLINICAL judgment ("was this necessary?").
Pressure form: a bill with a high-complexity E/M, a time-based code, or a test the patient may
not recall receiving.
Tyndale's correct behavior: translate each high-risk line item to plain language (the FACTUAL
meaning — "you were billed for the highest-complexity ER visit, which usually means a long,
intensive workup"), bundle the confirmation questions (P3), and convert a mismatch into a
candidate phantom-charge or upcoding finding. Ask only about facts the user can know from being
there.
A failure looks like: asking "was this medically necessary?"; assuming the service happened;
sequential one-at-a-time interrogation instead of a bundled confirmation.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "bill_error_detection" and `subcategory` = "encounter_verification".

For each case:
1. Construct a realistic user_message + a bill with a high-risk line item in case_file_state.
2. Include relevant user_profile.
3. Include case_file_state with the charged line items.
4. Define expected_output_traits — SHOULD translate to plain language + ask a factual confirmation;
   MUST NOT ask for a clinical judgment or assume the service occurred.
5. Provide expert_reasoning.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary the line-item type (E/M level, time-based, units, add-on, lab panel) and the
demographics; vary surface form and context depth.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
This IS a V1-Lite behavior (clinical data is Full V1). All cases should use the user-confirmation
path; the facts-not-clinical-judgment line is the key discriminator.
