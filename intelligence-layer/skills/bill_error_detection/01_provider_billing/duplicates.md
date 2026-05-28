# Duplicate charges

**What this is.** The same service is billed more than once for a single encounter —
either an exact duplicate line or the same service under two codes.

**Detection signals.**
- Identical code + date of service + units appearing on more than one line.
- The same service billed by both a facility and a professional claim without the
  expected professional/technical split.
- A re-submitted claim billed to the patient while the original is still processing.

**Citation language.** Tier A fact (the duplication is observable): "Line items 4 and 9
both bill CPT 80053 on 2026-03-14." A payer-policy citation supports non-payment of the
duplicate [payer claims-processing policy, src_TBD].

**Severity.** Low–medium (often clerical); high if repeated across statements.

**Common defenses.** Provider claims the services were distinct (e.g., bilateral, repeat).
Response: require documentation; a true repeat uses appropriate modifiers/units.

**Required evidence.** Itemized bill, the EOB, and any prior statement for the same visit.

**Recommended remediation (Tier C).** Request removal of the duplicate line; if already
paid, request a refund/adjustment. Escalate via `negotiation_strategy` if unresolved.
