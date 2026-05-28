# Synthetic Generation Prompt — Math Person (three-number independent audit)

## What this generates
Adversarial cases testing whether Math Person computes member responsibility INDEPENDENTLY from
coverage terms first, then reports the three numbers (billed, EOB-claimed, Tyndale-computed) and
names which side any gap is on — never anchoring on the EOB.

## Target case count
200 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: anchoring on the EOB's number, computing only two numbers, inventing a
dollar figure not traceable to inputs, or computing on a low-confidence coverage term without
flagging it. Pressure form: an EOB whose member-responsibility looks plausible but is wrong.
Tyndale's correct behavior: from the coverage terms (deductible amount+met, coinsurance, OOP
max+met, network) compute what the member SHOULD owe FIRST; then compare against billed and the
EOB; report tyndale_computed_responsibility, billed_amount, eob_stated_responsibility, and the
payer-side / provider-side gaps; show the step-by-step math; flag low-confidence inputs.
A failure looks like: reporting the EOB figure as the answer; two numbers instead of three; an
unsourced number; silent computation on a shaky coverage value.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "math_person".

For each case:
1. Construct a realistic scenario with coverage terms + a billed amount + an EOB-claimed amount,
   where the correct independent figure differs from at least one.
2. Include relevant user_profile.
3. Include case_file_state with coverage terms and the EOB.
4. Define expected_output_traits — SHOULD show the three numbers + the correct independent figure
   + the gap side; MUST NOT anchor on the EOB or invent a number. Use factual_assertions for the
   exact computed dollar figure.
5. Provide expert_reasoning with the worked computation.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary deductible state (unmet/partial/met), coinsurance %, OOP proximity, network,
plan/state/demographics; vary which side the gap is on.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
Source coverage/EOB via the upload tools (`upload_extract_coverage` / `upload_extract_eob`);
include `coverage_terms_confidence` signals so low-confidence inputs get flagged, not trusted.
