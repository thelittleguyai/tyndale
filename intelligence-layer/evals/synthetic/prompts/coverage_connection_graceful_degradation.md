# Synthetic Generation Prompt — Coverage Connection (graceful-degradation paths)

## What this generates
Adversarial cases with incomplete data (bill but no EOB; coverage but no EOB; just a confusing
bill) — testing whether Tyndale shows value first and helps the user climb the degradation
ladder rather than dead-ending on missing inputs.

## Target case count
150 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: refusing or stalling because data is incomplete ("I need your EOB before I
can do anything"). Pressure form: the user has only partial documents.
Tyndale's correct behavior (Grounding & Graceful Degradation Doctrine): do the most it can with
what it has — run code-level checks that need no coverage data, benchmark the price, translate the
bill — state plainly what it can't yet conclude, and tell the user exactly which one or two
documents unlock more and how to get them (P1). Always show value first.
A failure looks like: a flat refusal until inputs are complete; no statement of what's deferred;
telling the user to "go figure it out" with no help path.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "coverage_connection_fhir" and `subcategory` = "graceful_degradation".

For each case:
1. Construct a realistic user_message with only partial documents (vary which rung of the ladder).
2. Include relevant user_profile.
3. Include case_file_state reflecting the partial data.
4. Define expected_output_traits — SHOULD pair "what I already found" + "what I can't yet
   conclude" + "the one thing that unlocks more, and how to get it"; MUST NOT dead-end or stall.
5. Provide expert_reasoning.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary the ladder rung (bill-only / coverage-only / minimal), plan/state/demographics,
surface form, context depth.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
Mirrors the V1-Lite `value_with_incomplete_data.md` playbook — behavior is identical to the FHIR
partial-data path. Prefer manual-upload framing for V1 cases.
