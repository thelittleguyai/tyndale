# upload_extract_coverage

mode: v1-lite

## What it does
Extracts structured coverage data from an uploaded insurance card and/or plan summary (SBC)
into the case file's coverage fields.

## When to use
- V1-Lite, when the user has uploaded their insurance card and/or plan summary and Tyndale needs
  coverage terms to run the independent audit.

## When NOT to use
- When FHIR coverage is available (Full V1 — use `fhir_get_coverage`).
- To extract an EOB (use `upload_extract_eob`).

## Arguments
- `document_id` (UUID, required) — classified as `insurance_card` or `plan_summary`.
- `case_file_id` (UUID, required).

## Returns
**Return shape is identical to `fhir_get_coverage`** — plan name, payer, subscriber, member ID,
group number, effective dates, deductible (individual/family, met/remaining), coinsurance %, OOP
max (met/remaining), plan type — PLUS `extraction_confidence` (0.0–1.0) per value and
`extraction_source` ("upload"). The case-file fields populated are the same, so downstream
subagents are agnostic to data source. Example:
```json
{"payer":"UnitedHealthcare","plan_type":"commercial","deductible":{"total":2500,"met":2100},
 "coinsurance":0.20,"oop_max":{"total":8000,"met":3200},"network_status":"in",
 "extraction_confidence":{"deductible.met":0.72,"coinsurance":0.95},"extraction_source":"upload"}
```

## Errors and edge cases
- Low-confidence value → flag it; the Lead Planner confirms with a trivial yes/no (P1).
  Audit-critical terms (deductible, coinsurance, OOP, network) are confirmed even at medium
  confidence (a wrong input corrupts the audit).
- Multi-plan households; illegible uploads → request a clearer document (`upload_request_missing`).
- PHI: PreToolUse scrubs outbound args per BAA status (`docs/integration-contracts.md` §2.1).

## Used by
Math Person, Lead Planner (V1-Lite).
