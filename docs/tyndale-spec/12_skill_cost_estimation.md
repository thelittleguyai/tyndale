# Task 12 — Build the Cost Estimation Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** Tasks 01–11

## What this task does

Builds the Cost Estimation Skill — the playbook for estimating what a procedure should cost using FAIR Health UCR, plan benefits, and Medicare benchmarks. Returns a confident range with reasoning, not a guess.

## Prompt to paste into Claude Code

```
Create the Cost Estimation Skill in this repository.

Directory structure:

skills/cost_estimation/
├── SKILL.md
└── reference/
    ├── fair_health_lookup.md
    ├── medicare_rvu_lookup.md
    ├── plan_benefit_application.md
    ├── deductible_state_handling.md
    ├── coinsurance_oop_calculation.md
    ├── confidence_band_methodology.md
    └── edge_cases.md

For SKILL.md:

YAML frontmatter:
- name: cost_estimation
- description: "a little pushy" description. Covers estimating what a
  procedure should cost using FAIR Health UCR + plan benefits + Medicare
  RVU benchmarks. Returns a confident range with reasoning. When to use
  (user asks "what will this cost?" or "is this a fair price?"). When NOT
  to use (bill error detection, coverage application — those are separate
  Skills).
- version: 1.0.0

Body (under 500 lines):
- Intro: estimation methodology — start with FAIR Health UCR (geographic-
  and procedure-specific), apply user's plan benefits (deductible state,
  coinsurance, OOP max), cross-reference with Medicare RVU for sanity
  check
- References to foundation files
- Hard rule: every estimate includes a confidence band, never a point
  estimate. The user sees "expected range $1,800–$2,400" not "expected $2,100"
- Hard rule: every estimate cites its source data (FAIR Health for UCR;
  Medicare for benchmarks; the user's plan documents for benefits)
- Index of the 7 reference files with one-line descriptions

For each reference file in reference/:

Scaffold with relevant sections — about 40-60 lines per file:
- fair_health_lookup.md — how to query FAIR Health (3-digit ZIP fallback
  if no BAA), interpreting UCR data, edge cases
- medicare_rvu_lookup.md — how to look up Medicare allowable rates as a
  benchmark
- plan_benefit_application.md — how to apply the user's specific plan
  benefits to a raw UCR estimate
- deductible_state_handling.md — handling cases where deductible is
  partially met, fully met, not started
- coinsurance_oop_calculation.md — applying coinsurance percentages and
  out-of-pocket maximums
- confidence_band_methodology.md — how to construct the ±range around
  the point estimate (typically ±20% for routine procedures, ±35% for
  complex/variable procedures)
- edge_cases.md — multiple coverage, COB, mid-year plan changes,
  pre-deductible vs. post-deductible variations

Commit with message "Add Cost Estimation Skill".
```

## Done when

- `skills/cost_estimation/SKILL.md` and 7 reference files exist with proper structure
- Git log shows the commit

## Next task

[Task 13 — Build the Coverage Connection & FHIR Skill](13_skill_coverage_fhir.md)
