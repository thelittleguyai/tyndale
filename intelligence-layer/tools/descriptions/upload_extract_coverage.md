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
**Return shape is identical to `fhir_get_coverage`** — a `coverage` object (plan name, payer,
member ID, deductible/coinsurance/OOP amounts + met, network tier), a `coverage_terms_confidence`
object (`{overall, notes}`), and `raw_ocr` — PLUS an additive **`provenance`** block (DL-69):
`adapter`, `source_kind` (`user_upload` here), `as_of` (null for uploads), `confidence` (0.0–1.0),
`assumptions[]`. `provenance.adapter` names the data source (`UserUploadedSBC` today; a
OneUpHealth / eligibility adapter later) so downstream subagents stay source-agnostic. The
case-file fields populated are the same. Example:
```json
{"coverage":{"plan_name":"Acme PPO","payer_name":"UnitedHealthcare","member_id":"…",
  "deductible_amount":2500,"deductible_met":null,"coinsurance_percent":null,
  "oop_max_amount":null,"oop_max_met":null,"network_tier":null},
 "coverage_terms_confidence":{"overall":0.3,"notes":"V1-Lite OCR heuristics; user should confirm"},
 "provenance":{"adapter":"UserUploadedSBC","source_kind":"user_upload","as_of":null,
  "confidence":0.3,"assumptions":["V1-Lite OCR heuristics; user confirms low-confidence fields"]},
 "raw_ocr":{"…":"…"}}
```

## Errors and edge cases
- Low-confidence value → flag it; the Lead Planner confirms with a trivial yes/no (P1).
  Audit-critical terms (deductible, coinsurance, OOP, network) are confirmed even at medium
  confidence (a wrong input corrupts the audit).
- Multi-plan households; illegible uploads → request a clearer document (`upload_request_missing`).
- PHI: PreToolUse scrubs outbound args per BAA status (`docs/integration-contracts.md` §2.1).

## Used by
Math Person, Lead Planner (V1-Lite).
