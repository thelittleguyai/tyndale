# Bundling (unbundling / NCCI PTP)

**What this is.** Two or more services that should be paid as a single bundled
unit are billed separately, inflating the charge. Governed by CMS National Correct
Coding Initiative (NCCI) procedure-to-procedure (PTP) edits.

**Detection signals.**
- An NCCI PTP pair billed on the same date of service without a valid bypass modifier.
- A "column two" (component) code billed alongside its "column one" (comprehensive) code.
- Classic examples: simple closure billed with an excision; a lab panel plus its own components.
- Cross-check the `error_detection_rules` collection (narrative) + the NCCI tables in Postgres.

**Citation language.** Tier B: "These codes are an NCCI procedure-to-procedure pair and
should not be billed separately on the same date absent a documented distinct service
[CMS NCCI Policy Manual, src_TBD]."

**Severity.** Medium for an isolated pair; high if systematic across many claims (a
potential billing-fraud pattern).

**Common defenses.** Provider claims a "distinct procedural service" (modifier 59/XS/XU).
Response: require documentation of a separate site, session, or lesion; absent that, the
edit stands.

**Required evidence.** Itemized bill (not a summary), the operative/encounter note, and
the EOB showing how each line was allowed.

**Recommended remediation (Tier C).** Request a corrected claim from the provider; if
denied, sequence an appeal via the `negotiation_strategy` Skill. Frame as a recommendation
with reasoning, never an outcome prediction.
