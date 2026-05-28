# qdrant_search_payer_policies

mode: universal

## What it does
Searches the `payer_policies` Qdrant collection (CMS LCD/NCD + commercial medical-necessity
policies) for the policy chunks governing coverage of a service.

## When to use
- To check whether a service is covered/medically-necessary under the relevant payer's policy,
  or to ground a wrongful-denial finding.

## When NOT to use
- For statutes/regulations (use `qdrant_search_laws_regulations`); for code descriptors (use
  `qdrant_search_billing_codes`).

## Arguments
- `query` (string, required) — e.g. `"MRI knee medical necessity"`.
- `payer` (string, required) — e.g. `"UnitedHealthcare"` or `"Medicare"`.
- `effective_date` (date, **REQUIRED**) — the date of service. **The PreToolUse hook BLOCKS any
  query missing `effective_date`** (point-in-time correctness — `docs/integration-contracts.md`
  §2.1, rule 3).
- `applicable_codes` (array, optional); `max_results` (int, optional, default 10).

## Returns
```json
[{"chunk_id":"uhc_mri_knee_mednec","payer":"UnitedHealthcare","policy_id":"UHC-FIX-RAD-014",
  "version":"2025.1","chunk_text":"Knee MRI is medically necessary after a trial of conservative …",
  "effective_date_start":"2025-01-01","effective_date_end":null,"score":0.91}]
```

## Errors and edge cases
- Missing `effective_date` → **blocked by PreToolUse**; supply the date of service.
- Wrong plan year returned → the effective-date filter + rerank de-prioritize it; confirm the
  policy version matches the DOS.

## Used by
Bill Detective, Math Person, Lead Planner (V1-Lite — folded-in legal research).
