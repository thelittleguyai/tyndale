# Coverage resource parsing

> mode: shared — applies to both FHIR (full) and manual-upload (V1-Lite) modes. Both produce the same case-file coverage fields, so this parsing logic is identical regardless of source.

**What this covers.** Interpreting the FHIR `Coverage` resource (or the equivalent fields
extracted from an uploaded SBC / insurance card in V1-Lite) into the case file's coverage
fields.

**Fields to extract.**
- Plan name / payer, plan type (commercial / Medicare / Medicaid).
- Subscriber + member ID, group number.
- Effective dates (coverage period) — needed for date-of-service alignment.
- Cost-sharing terms where available: deductible, coinsurance, copays, out-of-pocket max,
  network tiers. (Some terms live in the SBC rather than the Coverage resource — combine sources.)

**Why it matters.** These terms are the **independent basis** Tyndale uses to compute what
the member SHOULD owe — the audit's foundation, not a convenience.

**Audit-critical fields.** Deductible (amount + met), coinsurance rate, OOP max (amount +
met), and network status feed the independent computation; they must be high-confidence
before the audit relies on them (see `extraction_confidence_handling.md`).
