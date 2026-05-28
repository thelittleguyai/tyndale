# MUE violations (units exceeding Medically Unlikely Edits)

**What this is.** A code is billed with more units than CMS Medically Unlikely Edits
(MUEs) consider plausible for a single patient on a single date of service.

**Detection signals.**
- Unit count above the MUE threshold for the code (check the MUE tables in Postgres +
  the `error_detection_rules` narrative).
- Implausible quantities (e.g., dozens of units of a once-per-day test).
- Unclassified/high-cost drug codes (e.g., J3490) with large unit counts and no detail.

**Citation language.** Tier B: "The billed units exceed the CMS Medically Unlikely Edit
for this code [CMS MUE, src_TBD]."

**Severity.** Medium; high for large-dollar drug/supply overcounts.

**Common defenses.** Provider claims a medically necessary repeat. Response: require
documentation supporting the quantity; MUE allows exceptions only with justification.

**Required evidence.** Itemized bill with units, the encounter note, and (for drugs) the
NDC and dosage.

**Recommended remediation (Tier C).** Request correction of the units; escalate via
`negotiation_strategy` if denied.
