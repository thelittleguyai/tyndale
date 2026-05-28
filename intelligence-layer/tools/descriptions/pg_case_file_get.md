# pg_case_file_get

mode: universal

## What it does
Reads a case file (or a filtered list of a user's case files) from Postgres, including its
documents, coverage, eobs, plan, research_log, findings, and deadlines.

## When to use
- At the start of any task to load the current state of a case.
- On app open, to load a returning user's open cases for the status-forward greeting.
- Before re-investigating, to read `research_log` and avoid redundant lookups.

## When NOT to use
- To write findings (use `pg_upsert_finding`) or deadlines (use `pg_deadline_upsert`).
- To list only upcoming deadlines (use `pg_list_due`).

## Arguments
- `case_file_id` (UUID, optional) — a single case, e.g. `"a1b2…0001"`.
- `user_id` (UUID, optional) — with `status_filter` to list a user's cases.
- `status_filter` (string|array, optional) — e.g. `["open","in_progress"]`.
(Provide `case_file_id` OR `user_id`+`status_filter`.)

## Returns
A case file record, or a list. Example:
```json
{"case_file_id":"a1b2…0001","status":"in_progress","coverage":{…},"eobs":[…],
 "research_log":[{"timestamp":"2026-03-14T…","topic":"deductible status","what_was_checked":"upload_extract_coverage","result_summary":"$2,100 of $2,500 met","finding_id":null}],
 "findings":[{"finding_id":"fnd_…","category":"cost_sharing_miscalculation"}]}
```

## Errors and edge cases
- Not found → `null` (single) or `[]` (list); never throws on a missing id.
- PHI: the returned record contains PHI; per `docs/integration-contracts.md` §2.1, outbound
  tool args are scrubbed by the PreToolUse hook before reaching external services (N/A for this
  internal read, but findings written downstream are audited via PostToolUse).

## Used by
All V1-Lite subagents — Lead Planner (V1-Lite), Bill Detective, Math Person.
