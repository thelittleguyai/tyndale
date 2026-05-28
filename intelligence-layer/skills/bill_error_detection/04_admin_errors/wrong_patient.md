# Wrong patient

**What this is.** The bill (or specific line items) belongs to a different patient — a
records mix-up or misattributed account.

**Detection signals.**
- Name, DOB, or account number that doesn't match the patient.
- Services or a provider the patient never saw.
- A date of service when the patient was not at the facility.

**Citation language.** Tier A fact (mismatch is observable). No legal citation needed
beyond the obligation to bill the correct patient; payer policy supports non-liability.

**Severity.** Medium (clerical), but blocks everything until resolved; can implicate
medical-record integrity.

**Common defenses.** Provider asserts the account is correct. Response: compare identifiers
and the patient's account of care.

**Required evidence.** The bill, the patient's ID, and the patient's account of whether the
care occurred.

**Recommended remediation (Tier C).** Demand correction/removal; ensure it isn't reported
to credit/collections. Sequence via `negotiation_strategy` if it persists.
