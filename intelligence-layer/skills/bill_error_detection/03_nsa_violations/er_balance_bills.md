# ER balance bills (No Surprises Act)

**What this is.** A patient is balance-billed for emergency services by an out-of-network
emergency provider/facility above the in-network cost-sharing amount — prohibited by the
No Surprises Act.

**Detection signals.**
- Emergency care at an out-of-network ER, with a bill above in-network cost-sharing.
- "Out-of-network" cost-sharing applied to emergency services.
- A balance-bill amount equal to billed-charge minus insurer payment.

**Citation language.** Tier B: "For emergency services, cost-sharing must be calculated as
if in-network and balance billing beyond that amount is prohibited [No Surprises Act,
42 U.S.C. §300gg-111(a), src_TBD]."

**Severity.** High (clear statutory protection; often large dollar).

**Common defenses.** Provider claims the patient consented or it wasn't an emergency.
Response: notice-and-consent is unavailable for emergency services.

**Required evidence.** EOB, the bill, and confirmation the care was emergency.

**Recommended remediation (Tier C).** Assert NSA protection; the provider/plan resolve the
balance via open negotiation / IDR (the patient is not a party). Sequence via
`negotiation_strategy` (`nsa_open_negotiation`).
