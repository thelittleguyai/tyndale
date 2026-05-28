# cost_estimate_medicare_rvu

mode: universal

## What it does
Returns the Medicare allowable rate for a procedure in a locality — a public, stable benchmark
for sanity-checking a FAIR Health UCR figure or a charge.

## When to use
- To anchor whether a charge/allowed amount is reasonable (commercial allowed is typically a
  multiple of Medicare); as a fallback when FAIR Health is unavailable.

## When NOT to use
- As the expected commercial price itself (it's a benchmark, not the estimate); to apply plan
  benefits.

## Arguments
- `cpt_code` (string, required) — e.g. `"73721"`.
- `geographic_locality` (string, required) — Medicare locality/GPCI region, e.g. `"01112"` (CA).

## Returns
```json
{"cpt_code":"73721","geographic_locality":"01112","medicare_allowable":284.50,"source":"Medicare PFS / RVU"}
```

## Errors and edge cases
- Unknown code/locality → error naming the bad input.
- Non-physician-fee-schedule code → note that Medicare RVU doesn't apply and use an alternate
  benchmark.

## Used by
Math Person, Lead Planner (V1-Lite).
