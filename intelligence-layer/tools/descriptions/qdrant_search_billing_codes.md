# qdrant_search_billing_codes

mode: universal

## What it does
Searches the `billing_codes` Qdrant collection for CPT/HCPCS/ICD-10 codes by code or descriptor,
returning matching records with descriptor + metadata.

## When to use
- To look up what a code means, confirm a descriptor, or find the code for a described service.

## When NOT to use
- To check bundling (use `ncci_check_pair`) or unit limits (use `mue_check`); to search rules
  (use `qdrant_search_error_detection_rules`).

## Arguments
- `query` (string, required) — a code or descriptor, e.g. `"70553"` or `"MRI brain with contrast"`.
- `max_results` (int, optional, default 10).

## Returns
```json
[{"code":"70553","code_system":"CPT","descriptor":"MRI of the brain with and without contrast",
  "category":"Radiology","score":0.93}]
```

## Errors and edge cases
- No match → `[]`; broaden the query or try the descriptor instead of the code.
- Ambiguous descriptor → multiple results; prefer exact code match (per the collection's rerank
  instruction). No effective_date required for this collection.

## Used by
Bill Detective. (Code Validator also uses it in Full V1.)
