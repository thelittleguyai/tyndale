# Place-of-service errors

**What this is.** The place-of-service (POS) code or facility/site-of-service is coded in
a way that inflates the allowed amount — e.g., an office service billed with a separate
facility fee, or a POS that triggers a higher payment.

**Detection signals.**
- A facility fee on a service performed in a non-facility (office) setting.
- POS code inconsistent with where care was actually delivered (per the patient).
- Provider-based billing for a service the patient experienced as a routine office visit.

**Citation language.** Tier B: "The place-of-service code does not match the site where
care was delivered, affecting the allowed amount [CMS POS code set / payer site-of-service
policy, src_TBD]."

**Severity.** Medium; can be high-dollar when a facility fee is added.

**Common defenses.** Provider asserts hospital-based/provider-based status. Response: ask
whether the patient was told they were being treated at a hospital outpatient department.

**Required evidence.** Itemized bill, the EOB, and the patient's account of where care occurred.

**Recommended remediation (Tier C).** Request correction of POS / removal of an improper
facility fee; escalate via `negotiation_strategy`.
