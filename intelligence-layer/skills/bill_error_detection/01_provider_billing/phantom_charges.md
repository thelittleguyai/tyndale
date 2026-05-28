# Phantom charges (services not rendered)

**What this is.** A charge for a service, item, or test the patient never received. The
clearest provider-side error and a fraud red flag. Tightly linked to encounter
verification (checks 0a/0b).

**Detection signals.**
- A line item the patient does not recognize and cannot account for from the visit.
- A test billed with no result on record; a supply billed but never dispensed.
- A service on a date the patient was not present.
- Run `06_encounter_verification/user_confirmation_flow.md` to confirm before asserting.

**Citation language.** Tier A fact once confirmed ("you were billed for X; you did not
receive X"). Non-payment for services not rendered is supported by payer policy and, in
egregious cases, false-claims standards [payer policy / 31 U.S.C. §3729 (context), src_TBD].

**Severity.** High — billing for services not rendered is the most serious category.

**Common defenses.** Provider claims the service was performed but undocumented. Response:
require documentation that it occurred; absent proof, the charge should be removed.

**Required evidence.** Itemized bill, the medical record / results, and the patient's
confirmation that the service did not occur.

**Recommended remediation (Tier C).** Demand removal; if a pattern, flag for escalation.
Sequence via `negotiation_strategy`.
