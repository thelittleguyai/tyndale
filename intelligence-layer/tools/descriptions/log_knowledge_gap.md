# log_knowledge_gap

mode: universal — available to all three subagents (lead_planner, bill_detective, math_person)

## What it does
Records that you hit a data gap, so the team learns what to ingest next. One row per gap.
Three gap types:
- `no_data` — a data/Qdrant query returned zero results
- `low_confidence` — you got results but the top score was below threshold
- `self_reported` — you reasoned "I don't have data on X"

## When to use
- **bill_detective**: a `qdrant_search_*` returns 0 hits, OR the top hit score < 0.5.
- **math_person**: a required input (e.g., the EOB allowed amount) is missing from case data.
- **lead_planner**: triage shows "I don't have data on X", or a subagent reports a gap upstream.

## When NOT to use
- For transient/retryable errors — that's not a knowledge gap.
- More than once for the same gap within a case — call once per distinct gap.

## Arguments
- `agent_name` (required): `lead_planner` | `bill_detective` | `math_person`
- `gap_type` (required): `no_data` | `low_confidence` | `self_reported`
- `query` (required): the specific thing you needed — keep it concrete (it clusters by first words)
- `context_summary`, `confidence_score`, `case_id`, `user_id` (optional)

## Returns
```json
{ "gap_id": "…", "logged": true }
```

## Notes
This is the feedback loop behind the Grounding & Graceful Degradation Doctrine: logging a gap
does NOT change your answer — keep serving the user with what you have and say plainly what you
can't yet conclude. The gap log just tells the team where the data holes are. It surfaces in the
admin gap dashboard and is marked resolved when ingestion closes it (e.g., `resolved_by_source =
"CO-2B Aetna policies"`).
