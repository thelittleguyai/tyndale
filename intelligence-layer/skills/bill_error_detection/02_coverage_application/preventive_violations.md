# Preventive-services cost-sharing violations

**What this is.** A preventive service that must be covered with zero cost-sharing
in-network (ACA §2713) is billed with a copay, coinsurance, or deductible.

**Detection signals.**
- Cost-sharing applied to a USPSTF Grade A/B service or recommended immunization, in-network.
- A screening colonoscopy reclassified to diagnostic (polyp removed) and charged cost-sharing.
- A preventive visit charged a copay.

**Citation language.** Tier B: "This is a covered preventive service that must be provided
without cost-sharing in-network [ACA §2713, 42 U.S.C. §300gg-13, src_TBD]; agency guidance
confirms a polyp removed during a screening colonoscopy does not create cost-sharing
[45 C.F.R. §147.130 guidance, src_TBD]."

**Severity.** Medium; clear legal basis makes it highly correctable.

**Common defenses.** Provider/insurer cite a diagnostic code. Response: cite the screening
intent and the polyp guidance.

**Required evidence.** EOB, the bill's codes, and the referral/screening intent.

**Recommended remediation (Tier C).** Request reprocessing as preventive; escalate via
`negotiation_strategy`.
