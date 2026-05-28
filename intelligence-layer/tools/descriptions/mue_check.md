# mue_check

mode: universal

## What it does
Structured lookup (Postgres MUE tables, not Qdrant) of whether the units billed for a code exceed
the CMS Medically Unlikely Edit for a given date of service.

## When to use
- To confirm a suspected over-units finding for a specific code.

## When NOT to use
- For bundling (use `ncci_check_pair`); for the policy narrative (use
  `qdrant_search_error_detection_rules`).

## Arguments
- `code` (string, required) — e.g. `"85025"`.
- `units_billed` (int, required) — e.g. `4`.
- `date_of_service` (date, required) — e.g. `"2026-03-14"`.

## Returns
```json
{"within_limit":false,"mue_value":1,"rationale":"CBC with differential is expected at most once per day; 4 units exceed the MUE."}
```

## Errors and edge cases
- Unknown code → error with the code named.
- Code with no published MUE → `mue_value:null`, `within_limit:true`, with a note that no edit
  applies.

## Used by
Bill Detective. (Code Validator in Full V1.)
