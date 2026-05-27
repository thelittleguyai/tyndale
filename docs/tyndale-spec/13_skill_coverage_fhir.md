# Task 13 — Build the Coverage Connection & FHIR Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** Tasks 01–12

## What this task does

Builds the Coverage Connection & FHIR Skill — the playbook for SMART-on-FHIR OAuth, parsing 1upHealth Coverage/EOB/Claim resources, and handling edge cases like multiple insurance plans or recent plan changes.

## Prompt to paste into Claude Code

```
Create the Coverage Connection & FHIR Skill in this repository.

Directory structure:

skills/coverage_connection_fhir/
├── SKILL.md
└── reference/
    ├── smart_on_fhir_oauth.md
    ├── coverage_resource_parsing.md
    ├── eob_resource_parsing.md
    ├── claim_resource_parsing.md
    ├── multi_coverage_cob.md
    ├── recent_plan_changes.md
    └── connection_troubleshooting.md

For SKILL.md:

YAML frontmatter:
- name: coverage_connection_fhir
- description: "a little pushy" description. Covers SMART-on-FHIR OAuth
  flow, parsing 1upHealth FHIR resources (Coverage, EOB, Claim,
  ExplanationOfBenefit), handling edge cases like multiple coverages,
  recent plan changes, COB (coordination of benefits). When to use
  (any time Tyndale needs to pull or refresh a user's insurance data).
  When NOT to use (cost estimation, bill error detection — those are
  separate Skills).
- version: 1.0.0

Body (under 500 lines):
- Intro: 1upHealth is the sole FHIR provider at V1
- OAuth flow overview (SMART-on-FHIR app launch sequence)
- Standard FHIR resources Tyndale pulls: Coverage, ExplanationOfBenefit,
  Claim, ClinicalNote (when relevant)
- AUDIT-BASIS STATEMENT (per the Independent Audit Doctrine in
  reference/principles.md): the EOB/ExplanationOfBenefit resource Tyndale
  pulls is the insurer's CLAIM, to be audited — not the source of truth.
  Even with clean FHIR data, Math Person computes member responsibility
  independently from the Coverage resource terms first, then compares
  against the EOB. FHIR makes the data cleaner; it does NOT make the
  insurer's math correct.
- GRACEFUL-DEGRADATION STATEMENT (per the Grounding & Graceful
  Degradation Doctrine): FHIR pulls are not always complete. The EOB for
  a recent visit may not have posted yet; a payer may return partial
  resources; clinical notes may be unavailable. When FHIR data is
  partial, Tyndale degrades exactly the same way the V1-Lite manual path
  does — it does the most it can with what it has, states what it can't
  yet conclude, and tells the user what's pending and when it'll likely
  resolve (e.g., "your insurer hasn't posted the EOB for this visit yet —
  I'll re-check automatically, but here's what I can already tell you from
  the bill's codes"). Never dead-end the user just because a FHIR resource
  is missing.
- Edge cases that warrant special handling
- Reference to engineering team note: actual OAuth implementation is
  built by the engineers; this Skill describes WHAT to do with the data
  once retrieved

For each reference file in reference/:

About 40-60 lines per file:
- smart_on_fhir_oauth.md — the OAuth handshake sequence, token storage,
  refresh flow (Skill describes flow; engineers implement)
- coverage_resource_parsing.md — fields in Coverage resource (plan name,
  subscriber, effective dates, group number), what to extract. Note: this
  parsing logic is SHARED with V1-Lite's manual-upload mode, which
  produces the same case file fields.
- eob_resource_parsing.md — fields in ExplanationOfBenefit resource,
  parsing line items, allowed amounts, member responsibility. Note: parse
  the EOB to extract the insurer's CLAIMED figures so they can be COMPARED
  against Tyndale's independent computation — never adopted as the answer.
- claim_resource_parsing.md — Claim vs EOB distinction, status fields
- multi_coverage_cob.md — when a user has multiple insurance plans,
  primary vs secondary determination, COB sequencing
- recent_plan_changes.md — handling mid-year plan changes, gap periods,
  retroactive coverage
- partial_fhir_data.md — the graceful-degradation playbook for FHIR:
  which analyses Tyndale can still run when only some resources returned
  (e.g., Coverage present but EOB not yet posted), what to tell the user
  is pending, and when to auto-re-check (ties into the Proactive Monitor
  cron). Mirrors V1-Lite's value_with_incomplete_data.md so behavior is
  identical across modes.
- connection_troubleshooting.md — common error patterns and how to
  surface them to the user (e.g., expired tokens, payer-side rate limits)

Commit with message "Add Coverage Connection & FHIR Skill (audit-basis + graceful degradation)".
```

## Done when

`skills/coverage_connection_fhir/SKILL.md` and 8 reference files exist (including partial_fhir_data.md). The audit-basis and graceful-degradation statements are present. Git log shows the commit.

## Next task

[Task 14 — Build the Find a Doctor Skill](14_skill_find_a_doctor.md)
