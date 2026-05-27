# Task 14 — Build the Find a Doctor Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** Tasks 01–13

## Prompt to paste into Claude Code

```
Create the Find a Doctor Skill in this repository.

Directory structure:

skills/find_a_doctor/
├── SKILL.md
└── reference/
    ├── in_network_search.md
    ├── provider_directory_validation.md
    ├── quality_data_sources.md
    ├── specialty_taxonomy.md
    ├── tier_verification.md
    └── ghost_network_detection.md

For SKILL.md:

YAML frontmatter:
- name: find_a_doctor
- description: "a little pushy" description. Covers finding in-network
  providers — search by specialty, location, quality data, and verifying
  network status against the user's specific plan. When to use (user
  needs a doctor for a specific need). When NOT to use (this is not
  appointment booking — it's provider identification + network status
  verification). Lead Planner calls this directly without subagent
  delegation since the task is well-scoped.
- version: 1.0.0

Body (under 500 lines):
- Intro: provider search uses NPI registry + payer directories + quality
  data (CMS Care Compare, Healthgrades public data); cross-references
  network status against the user's plan
- GROUNDING STATEMENT (per the Grounding Doctrine in
  reference/principles.md): every provider, network status, and quality
  signal Tyndale returns is grounded in a real source — the NPI registry
  for identity/licensure, the payer's own directory for network status,
  CMS Care Compare for quality. Tyndale NEVER recommends a provider from
  the model's general knowledge ("I think Dr. X is good"), because that's
  exactly the ungrounded behavior that makes a raw LLM unreliable here.
  If a provider can't be grounded in these sources, Tyndale doesn't
  surface them. Name the source for each result.
- Important: "ghost networks" are a real problem — providers listed in
  payer directories who aren't actually accepting patients. Tyndale
  attempts to detect and warn when this is likely
- Reference to engineering note: actual provider search tool
  implementation is built by engineers; this Skill describes the search
  strategy

For each reference file in reference/:

About 40-60 lines per file:
- in_network_search.md — querying payer provider directories
- provider_directory_validation.md — cross-checking directory data
  against NPI registry, recent state license verification
- quality_data_sources.md — CMS Care Compare, public quality reports
- specialty_taxonomy.md — matching user's need to the right specialty
  (e.g., "knee pain" → orthopedic surgeon vs sports medicine vs
  physiatry depending on context)
- tier_verification.md — confirming the provider's tier in tiered
  network plans
- ghost_network_detection.md — signals that a provider may not actually
  be accepting patients; how to surface this to the user

Commit with message "Add Find a Doctor Skill".
```

## Done when

`skills/find_a_doctor/SKILL.md` and 6 reference files exist. Git log shows the commit.

## Next task

[Task 15 — Build the Plan a Visit Skill](15_skill_plan_a_visit.md)
