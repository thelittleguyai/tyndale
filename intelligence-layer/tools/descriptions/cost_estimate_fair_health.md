# cost_estimate_fair_health

mode: universal

## What it does
Returns a FAIR Health UCR (usual, customary, reasonable) estimate for a procedure in a geography,
as a confidence band — the starting point for a cost estimate.

## When to use
- To benchmark what a procedure should cost, or to judge whether an allowed amount is reasonable.

## When NOT to use
- For the Medicare benchmark (use `cost_estimate_medicare_rvu`); to apply the user's plan
  benefits (that's the Cost Estimation Skill's `plan_benefit_application` logic).

## Arguments
- `cpt_code` (string, required) — e.g. `"73721"`.
- `geographic_zip` (string, required) — **3-digit ZIP if no FAIR Health BAA, full 5-digit if a
  BAA is executed.** e.g. `"945"` (no BAA) or `"94538"` (BAA).

## Returns
```json
{"cpt_code":"73721","geographic_zip":"945","ucr_point":1150,"confidence_band":{"low":920,"high":1380},
 "percentile_used":80,"precision":"3-digit-zip","source":"FAIR Health"}
```

## V1-Lite note
Until the FAIR Health BAA executes (a Brock parallel track), queries use **3-digit ZIP precision
(HIPAA Safe Harbor)** — `precision:"3-digit-zip"`. With a BAA, full 5-digit ZIP is used. Always
present the result as a band, never a point estimate.

## Errors and edge cases
- No FAIR Health data for the code/area → fall back to `cost_estimate_medicare_rvu` and say so.
- PHI: the PreToolUse hook scrubs outbound args and enforces 3-digit-ZIP when no BAA is on file
  (`docs/integration-contracts.md` §2.1).

## Used by
Math Person, Lead Planner (V1-Lite, via the Cost Estimation Skill).
