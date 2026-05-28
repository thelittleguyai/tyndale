# Modifier abuse (25, 59, 51)

**What this is.** Modifiers used to unlock separate payment when the clinical facts don't
support them — most commonly modifier 25 (separate E/M same day as a procedure), 59
(distinct procedural service), and 51 (multiple procedures).

**Detection signals.**
- Modifier 25 attached to an E/M on the same day as a minor procedure as a matter of routine.
- Modifier 59 used specifically to bypass an NCCI edit on the same site/lesion.
- Missing expected multiple-procedure payment reduction when modifier 51 applies.

**Citation language.** Tier B: "Modifier 25 requires a significant, separately
identifiable E/M beyond the usual pre/post-procedure work [CMS modifier guidance / NCCI
Policy Manual, src_TBD]."

**Severity.** Medium; high if systematic (a known overpayment driver).

**Common defenses.** Provider asserts the E/M or service was separate. Response: require
documentation that the E/M was above-and-beyond, or that 59 reflects a different
site/session.

**Required evidence.** Itemized bill, the encounter note, and the EOB.

**Recommended remediation (Tier C).** Request a corrected claim removing the unsupported
modifier; escalate via `negotiation_strategy`.
