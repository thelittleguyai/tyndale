# The EOB is audited, not trusted

> mode: shared in spirit (stated here for the coverage Skill; the doctrine governs all modes).

**The Independent Audit Doctrine, applied to coverage.** The EOB is the **insurer's CLAIM**
about what was covered and what the member owes. It is an **audited input, never ground
truth**. Tyndale uses the coverage terms to compute **independently** what the member SHOULD
owe, then treats any gap between that figure and the EOB as a **candidate payer-side finding**.

**Why this matters.** An ordinary person reads the EOB's "member responsibility" and assumes
the insurer did the math right. Half of what Tyndale exists to catch is exactly the insurer's
mistakes — cost-sharing miscalculations, coverage misapplied, wrongful denials, network
mis-processing, OOP-max ignored. If Tyndale trusted the EOB, it would be blind to all of them.

**Three numbers, always.** What the provider billed · what the EOB claims the member owes ·
what Tyndale independently computes the member should owe. A gap with the EOB → payer-side
finding; a gap with the bill → provider-side finding. Both are pursued.

**Cross-reference.** Payer-side detection lives in
`skills/bill_error_detection/05_payer_side_errors/` (cost-sharing miscalculation, coverage
misapplied, wrongful denial, network-status error, OOP-max ignored). The coverage terms
acquired here are what make those checks possible.
