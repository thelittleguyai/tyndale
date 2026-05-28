# pg_deadline_upsert

mode: universal

## What it does
Writes (or updates) a deadline on a case file in Postgres so the Proactive Monitor cron can track
and notify on it.

## When to use
- Whenever a finding triggers a statutory or procedural deadline (appeal window, filing window,
  charity-care application window).

## When NOT to use
- To compute the deadline date (use `deadline_calculate` first); to list upcoming deadlines (use
  `pg_list_due`).

## Arguments
- `case_file_id` (UUID, required).
- `deadline_date` (date, required) — e.g. `"2026-09-12"`.
- `deadline_type` (string, required) — e.g. `"erisa_internal_appeal"`.
- `description` (string, required) — e.g. `"180-day internal appeal window for claim CLM-…"`.

## Returns
```json
{"deadline_id":"ddl_3a…"}
```

## Errors and edge cases
- Unknown `case_file_id` → foreign-key error.
- A `deadline_date` in the past → accepted but flagged so the Lead Planner can surface it as
  overdue.

## Used by
Lead Planner (V1-Lite — folded-in strategy). (Strategist in Full V1.)
