# provider_340b_check

mode: universal

## What it does
Checks whether a provider participates in the 340B Drug Pricing Program (which can support a
pricing/negotiation argument on drug-related charges).

## When to use
- When a 340B-pricing argument may apply to drug charges from a participating provider.

## When NOT to use
- For non-drug charges; as a coverage or medical-necessity check (use `qdrant_search_payer_policies`).

## Arguments
- `provider_npi` (string, optional) — e.g. `"1234567890"`.
- `provider_name` + `state` (optional) — when the NPI is unknown.
(Provide `provider_npi` OR `provider_name`+`state`.)

## Returns
```json
{"is_340b_eligible":true,"program_details":{"entity_type":"DSH hospital","covered_entity_id":"DSH123456"}}
```

## Errors and edge cases
- No match → `is_340b_eligible:false` with a note that participation couldn't be confirmed.
- Ambiguous name → return candidates and ask the Lead Planner to confirm the NPI.

## Used by
Lead Planner (V1-Lite — folded-in strategy). (Strategist in Full V1.)
