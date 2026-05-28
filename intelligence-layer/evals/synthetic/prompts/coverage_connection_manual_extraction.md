# Synthetic Generation Prompt — Coverage Connection (manual-mode extraction edge cases)

## What this generates
Adversarial cases for the V1-Lite manual-upload coverage path: low-confidence extractions,
multi-plan households, illegible uploads — testing whether Tyndale confirms audit-critical terms
(per P1) before relying on them.

## Target case count
150 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: silently computing on a shaky extracted coverage value, or asking a
clumsy multi-part question instead of a trivial confirmation. Pressure form: an uploaded card/SBC
with a low-confidence deductible/coinsurance/OOP/network value, or two plans in the household.
Tyndale's correct behavior: handle extraction_confidence — assert high-confidence silently; for
audit-critical terms (deductible amount+met, coinsurance, OOP max+met, network status), confirm
even at medium confidence with ONE trivial yes/no (P1, "I read your deductible as $2,500 — is
that right?"); bundle multiple confirmations (P3). Resolve primary vs. secondary for multi-plan.
A failure looks like: computing the audit on a low-confidence value without confirming; a
sequence of separate questions; demanding the user "figure it out."

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "coverage_connection_fhir" and `subcategory` = "manual_extraction".

For each case:
1. Construct a realistic user_message + an uploaded coverage doc with per-field
   extraction_confidence in case_file_state.
2. Include relevant user_profile.
3. Include case_file_state with the extracted-coverage fields + confidences.
4. Define expected_output_traits — SHOULD confirm audit-critical low/medium-confidence terms with
   a trivial bundled question; MUST NOT silently rely on them or interrogate.
5. Provide expert_reasoning.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary which term is low-confidence, plan/state/demographics, single vs. multi-plan,
surface form.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
This is a core V1-Lite path (manual upload). Use `upload_extract_coverage` semantics and the
extraction_confidence field; FHIR-pull cases are out of scope for V1 here.
