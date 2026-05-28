# Coverage misapplied (PAYER-SIDE)

**What this is.** The insurer processed the claim under the wrong benefit — wrong benefit
category, wrong plan year, or a benefit simply ignored. The EOB's framing is the insurer's
claim; the detection signal is a GAP between how the benefit WAS applied and how the plan
says it SHOULD apply.

**Detection signals.**
- A service paid under the wrong benefit category (e.g., specialty vs. preventive).
- The wrong plan-year accumulators used (claim straddles a plan change).
- A benefit the SBC provides that the EOB never applied.

**Citation language.** Tier B: "Under the plan's benefit design, this service falls under
[benefit]; the EOB applied [wrong benefit], contrary to the SBC [plan SBC, src_TBD]."

**Severity.** High — can convert a covered service into a large patient balance.

**Common defenses.** Insurer asserts its categorization. Response: cite the SBC's benefit
definition and the date of service / plan year.

**Required evidence.** EOB, SBC/benefit booklet, and the date of service.

**Recommended remediation (Tier C).** Request reprocessing under the correct benefit/plan
year; escalate via `negotiation_strategy`.
