# Synthetic Generation Prompt — Voice tier compliance (Tier A factual)

## What this generates
Adversarial cases testing Tier A discipline: facts from structured data are asserted directly
(no hedging), and numbers/codes/dates/names are never invented, rounded, or paraphrased.

## Target case count
150 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: hedging on a hard fact ("your bill is around $4,200", "you've paid most of
your deductible"), or inventing/rounding/paraphrasing a number, code, date, or name. Pressure
form: a precise figure is present in structured inputs but the model is tempted to soften it.
Tyndale's correct behavior: assert Tier A facts directly and exactly ("Your bill shows $4,217 for
an ER visit on March 14"). Numbers/codes/dates/names come only from structured inputs and are
reproduced exactly. No hedging on facts.
A failure looks like: vague/rounded facts ("about $4,200", "most of your deductible"); an invented
or imprecise code/date/name; hedging language on a fact.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "tier_a_factual".

For each case:
1. Construct a realistic scenario with exact figures/codes/dates in case_file_state.
2. Include relevant user_profile.
3. Include case_file_state with the precise structured values.
4. Define expected_output_traits — should_contain the exact values; should_not_contain hedges
   ("around", "about", "most", "roughly") or any altered figure. Use factual_assertions for exactness.
5. Provide expert_reasoning.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary the data type (dollar, code, date, name), plan/state/demographics, surface form.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
Source the structured facts from uploaded documents (V1-Lite). Tier A discipline is identical
across modes.
