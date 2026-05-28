# pg_upsert_finding

mode: universal

## What it does
Writes (or updates) a structured finding on a case file in Postgres and returns its id.

## When to use
- Whenever a subagent identifies a finding (provider-side, payer-side, or encounter mismatch)
  it must persist for the Lead Planner to read when composing the answer.

## When NOT to use
- For the running coverage math summary (that's a finding too, but cost-sharing detail goes in
  the finding's `facts`); not for deadlines (use `pg_deadline_upsert`).

## Arguments
- `case_file_id` (UUID, required).
- `finding` (dict, required) — `{finding_type, category, voice_tier, facts, legal_claim?, recommendation?, status?}`.
- `subagent_source` (string, required) — e.g. `"bill_detective"`.

## Returns
```json
{"finding_id":"fnd_8f3e7"}
```
On update of an existing finding (same key), the same `finding_id` is returned.

## Errors and edge cases
- Invalid `voice_tier` (not A/B/C) or `finding_type` → validation error (the DB CHECK
  constraints enforce these).
- Unknown `case_file_id` → foreign-key error.
- PHI: the write is audited via the PostToolUse hook (`docs/integration-contracts.md` §2.1/§2.2);
  `facts` may contain PHI and is handled per BAA status.

## Used by
All V1-Lite subagents — Lead Planner (V1-Lite), Bill Detective, Math Person.
