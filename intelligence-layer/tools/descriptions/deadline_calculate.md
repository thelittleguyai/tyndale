# deadline_calculate

mode: universal

## What it does
Computes a deadline date from a triggering event and a deadline type, with the reasoning (which
rule sets the window).

## When to use
- Before `pg_deadline_upsert`, to derive the correct date for an appeal/filing window.

## When NOT to use
- To persist the deadline (use `pg_deadline_upsert`); to list deadlines (use `pg_list_due`).

## Arguments
- `triggering_event_date` (date, required) — e.g. denial date `"2026-03-20"`.
- `deadline_type` (enum, required) — `erisa_internal_appeal | aca_external_review |
  nsa_negotiation | nsa_idr | …`.
- `jurisdiction` (string, optional) — for state-specific windows.

## Returns
```json
{"calculated_deadline_date":"2026-09-16","reasoning":"ERISA gives 180 days from the date of an adverse benefit determination to file an internal appeal [29 C.F.R. §2560.503-1(h)]."}
```

## Errors and edge cases
- Unknown `deadline_type` → error listing supported types.
- State-specific window without `jurisdiction` → returns the federal default and flags the
  assumption.

## Used by
Lead Planner (V1-Lite — folded-in strategy). (Strategist in Full V1.)
