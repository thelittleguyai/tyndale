# cost_estimate_trilliant

mode: universal — STUB (not wired)

## What it does
Placeholder for the Trilliant procedure-level price vendor. NOT implemented — raises
`NotImplementedError`. Trilliant is hands-off per DL-50 (contract pending; Brock surfaces
when live). The `estimate_cost()` query layer already skips `source='trilliant'` rows.

## When to use
- Never (yet). Use `cost_estimate_combined` for the working cost path.

## Notes
When Trilliant lands (CO-3B), this adapter ingests its data into `transparency_rates`
(source=`trilliant`) and the query layer picks it up automatically. Replaces the
deprecated `cost_estimate_fair_health` (DL-50: Trilliant replaced FAIR Health).
