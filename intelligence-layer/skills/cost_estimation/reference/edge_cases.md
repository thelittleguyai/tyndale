# Cost-estimation edge cases

**Multiple coverage / coordination of benefits (COB).** When the user has two plans,
estimate against the **primary** plan first, then the secondary's contribution. Determine
primary vs. secondary per COB rules (see Coverage Connection's `multi_coverage_cob.md`).
Widen the band — secondary contributions are harder to predict.

**Mid-year plan changes.** If the service date falls near a plan change, use the benefits in
effect **on the date of service**, including the correct year's accumulators (deductible /
OOP reset). A new plan year resets amounts-met to $0.

**Pre-deductible vs. post-deductible.** State which the estimate assumes — the same service
costs very differently before vs. after the deductible is met. If the deductible status is
uncertain, present both scenarios or widen the band and say so.

**Self-pay / uninsured.** No benefits to apply — estimate against UCR/Medicare and surface
the cash-pay / Good Faith Estimate angle. Route to charity-care paths if relevant.

**Bundled vs. itemized.** A "global" surgical fee may or may not include anesthesia,
pathology, and facility fees. Note which components the estimate covers and flag likely
add-ons so the user isn't surprised (per P2 — surface what's next).

**Rule throughout.** Every edge case still yields a sourced **range**, not a point estimate,
with the assumptions named.
