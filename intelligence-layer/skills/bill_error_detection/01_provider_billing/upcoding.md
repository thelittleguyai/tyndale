# Upcoding (E/M level / complexity higher than supported)

**What this is.** A service is coded at a higher level (or higher-complexity variant)
than the documentation or the actual visit supports — e.g., a level-5 visit for a brief,
single-problem encounter.

**Detection signals.**
- High-level E/M (99204/99205, 99214/99215, 99285) for a short or routine visit.
- Time-based code selection where the billed level exceeds the documented total time.
- A pattern of the same high level across many visits regardless of complexity.
- Run encounter verification (`06_encounter_verification/`) to compare the coded level
  with the patient's account.

**Citation language.** Tier B (coding rule): "The documented medical decision making /
total time does not support the billed E/M level under CPT E/M guidelines [AMA CPT E/M
guidelines, src_TBD]."

**Severity.** Medium; high if part of a systematic pattern.

**Common defenses.** Provider cites complexity or comorbidities. Response: ask for the
note supporting the level; compare to the patient's lived account of the visit.

**Required evidence.** Itemized bill, the visit/encounter note, and the patient's
description of the visit (duration, what was done).

**Recommended remediation (Tier C).** Request a recode/corrected claim; escalate via
`negotiation_strategy` if denied.
