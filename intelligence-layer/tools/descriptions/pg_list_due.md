# pg_list_due

mode: universal

## What it does
Lists a user's upcoming (and overdue) deadlines from Postgres within a window.

## When to use
- On app open, to drive the status-forward greeting (Change Order 001 item 3).
- By the Proactive Monitor cron to fire threshold notifications (14d/7d/3d/24h).

## When NOT to use
- To create a deadline (use `pg_deadline_upsert`); to load a full case file (use
  `pg_case_file_get`).

## Arguments
- `user_id` (UUID, optional) — omit to scan all users (cron).
- `within_days` (int, optional, default 30).

## Returns
```json
[{"deadline_id":"ddl_3a…","case_file_id":"a1b2…","deadline_date":"2026-06-12",
  "deadline_type":"erisa_internal_appeal","days_remaining":9,"status":"pending"}]
```

## Errors and edge cases
- No upcoming deadlines → `[]`.
- Overdue items are included with negative `days_remaining` so they surface first.

## Used by
Lead Planner (V1-Lite), Proactive Monitor cron.
