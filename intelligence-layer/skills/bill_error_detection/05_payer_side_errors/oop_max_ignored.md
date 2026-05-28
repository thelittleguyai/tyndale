# Out-of-pocket maximum ignored (PAYER-SIDE)

**What this is.** The insurer charged cost-sharing after the patient had already met their
out-of-pocket maximum, or failed to count eligible cost-sharing toward the OOP max. The EOB
is the insurer's claim; the detection signal is a GAP between the OOP accumulator and the
cost-sharing charged.

**Detection signals.**
- Cost-sharing on the EOB after the OOP max was met for the plan year.
- Eligible amounts not credited to the OOP accumulator.
- Tyndale's running OOP total (from prior EOBs) shows the max reached.

**Citation language.** Tier B: "Once the out-of-pocket maximum is met, the plan must cover
100% of in-network essential benefits; the EOB charges cost-sharing past that point [plan
SBC; ACA OOP-max rules, src_TBD]."

**Severity.** High — once OOP is met, the correct member responsibility is often $0.

**Common defenses.** Insurer cites accumulator timing or non-EHB exclusions. Response:
provide the amounts-met and the dates.

**Required evidence.** Current and prior EOBs, the SBC, and the OOP amount-met.

**Recommended remediation (Tier C).** Request reprocessing with the OOP max applied;
escalate via `negotiation_strategy`.
