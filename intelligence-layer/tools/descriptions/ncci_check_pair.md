# ncci_check_pair

mode: universal

## What it does
Structured lookup (Postgres NCCI tables, not Qdrant) of whether two codes form an NCCI
procedure-to-procedure edit and whether a modifier may bypass it on a given date of service.

## When to use
- To definitively confirm a suspected bundling/unbundling finding for a specific code pair.

## When NOT to use
- For the policy reasoning/narrative (use `qdrant_search_error_detection_rules`); for unit limits
  (use `mue_check`).

## Arguments
- `code_a` (string, required) — e.g. `"11402"`.
- `code_b` (string, required) — e.g. `"12031"`.
- `date_of_service` (date, required) — e.g. `"2026-03-14"` (NCCI edits change quarterly).

## Returns
```json
{"bundling_status":"modifier_allowed","applicable_modifier":"59","ncci_edit_reference":"PTP 11402/12031 (2026Q1)"}
```
`bundling_status` ∈ {bundled, not_bundled, modifier_allowed}.

## Errors and edge cases
- Unknown code → error with the offending code named.
- `date_of_service` outside loaded NCCI quarters → returns the nearest applicable quarter and
  flags the assumption.

## Used by
Bill Detective. (Code Validator in Full V1.)
