# Recent plan changes

> mode: shared — applies to both FHIR and manual modes.

**What this covers.** Handling mid-year plan changes, coverage gaps, and retroactive coverage
so the correct terms are applied to each date of service.

**Key rules.**
- **Use the plan in effect on the DATE OF SERVICE**, not the plan in effect today.
- A new plan year **resets accumulators** — deductible and OOP-max amounts-met return to $0.
  A claim straddling the change must use the correct year's accumulators.
- **Gap periods:** a service during an uninsured gap has no benefits to apply → route to
  cost-estimation / self-pay / charity-care paths.
- **Retroactive coverage:** if coverage was applied retroactively, claims may need
  resubmission; the corrected EOB is the audited input.

**Audit note.** Applying the wrong plan year's terms is a frequent payer error (coverage
misapplied) — see `bill_error_detection/05_payer_side_errors/coverage_misapplied.md`. Always
confirm which plan/year governs the DOS before computing.
