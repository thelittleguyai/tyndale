# legal_doi_complaint_route

mode: universal

## What it does
Returns the applicable state Department of Insurance (DOI) office and a summary of its complaint
procedure for the user's state and plan type.

## When to use
- When a payer is unresponsive or a state DOI complaint is a viable escalation path for a
  fully-insured/commercial plan.

## When NOT to use
- For self-funded ERISA plans (DOI generally lacks jurisdiction — use the ERISA appeal /
  DOL path); to route the user to a specific ombudsman or attorney (out of scope per refusals).

## Arguments
- `user_state` (string, required) — e.g. `"UT"`.
- `payer_type` (enum, required) — `commercial | medicaid | medicare | self_funded`.

## Returns
```json
{"applicable":true,"doi_office":"Utah Insurance Department","complaint_procedure":"File a consumer complaint online or by mail; the DOI requests a response from the insurer …","note":"Self-funded ERISA plans fall under DOL, not the state DOI."}
```

## Errors and edge cases
- `payer_type:"self_funded"` → `applicable:false` with the ERISA/DOL note (the DOI generally has
  no jurisdiction).
- Keep output to scope facts; do not route to a specific person.

## Used by
Lead Planner (V1-Lite — folded-in legal/strategy). (Legal Researcher / Strategist in Full V1.)
