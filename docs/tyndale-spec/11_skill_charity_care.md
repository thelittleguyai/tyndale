# Task 11 — Build the Charity Care Eligibility Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** Tasks 01–10

## What this task does

Builds the Charity Care Eligibility Skill — the playbook for determining whether a user qualifies for hospital charity care under IRS 501(r) requirements. Includes a diagnostic index (does this hospital even qualify? does this user meet income/asset tests?).

## Prompt to paste into Claude Code

```
Create the Charity Care Eligibility Skill in this repository.

Directory structure:

skills/charity_care_eligibility/
├── SKILL.md
├── 00_diagnostic_index.md
└── reference/
    ├── irs_501r_framework.md
    ├── hospital_tax_status_check.md
    ├── fap_retrieval_strategies.md
    ├── agi_fpl_calculation.md
    ├── asset_tests.md
    ├── residency_requirements.md
    ├── state_specific_overlays.md
    ├── application_process.md
    ├── retroactive_charity_care.md
    └── appeal_process.md

For SKILL.md:

YAML frontmatter:
- name: charity_care_eligibility
- description: "a little pushy" description. Covers determining whether
  a user qualifies for hospital charity care under IRS 501(r). Covers
  hospital tax status, FAP retrieval, AGI/FPL calculation, asset tests,
  state-specific overlays. When to use (any time a user faces an
  unaffordable hospital bill and the provider might be a nonprofit
  501(c)(3) hospital). When NOT to use (private/for-profit providers —
  use direct_provider_negotiation framework instead). ALWAYS load
  00_diagnostic_index.md first.
- version: 1.0.0

Body (under 500 lines):
- Intro: this Skill determines charity care eligibility before
  recommending the application path
- Reference to reference/principles.md, reference/voice_tiering.md,
  reference/citations.md, reference/glossary.md (specifically IRS §501(r)
  citations)
- Two-layer architecture: diagnostic first, then specific reference files

For 00_diagnostic_index.md:

Diagnostic questions:

1. Is this provider a nonprofit 501(c)(3) hospital?
   → If yes, IRS §501(r) requirements apply
   → If no, charity care under federal law not available — recommend
     direct provider negotiation instead
   → How to check: hospital_tax_status_check.md

2. Has the hospital published a Financial Assistance Policy (FAP)?
   → If yes, the FAP defines specific eligibility thresholds
   → If no, this is itself a 501(r) violation — flag to legal
   → How to retrieve: fap_retrieval_strategies.md

3. Is the user's household income at or below the FAP's threshold?
   → Most FAPs use 200-400% of Federal Poverty Level (FPL)
   → Some use lower thresholds; some have asset tests
   → How to calculate: agi_fpl_calculation.md

4. Does the FAP require asset tests, and does the user meet them?
   → How to evaluate: asset_tests.md

5. Does the user meet residency requirements?
   → Most FAPs require state or county residency
   → How to verify: residency_requirements.md

6. Are there state-specific charity care laws that apply?
   → Some states have additional requirements (CA, IL, NJ, NY notably)
   → How to check: state_specific_overlays.md

7. Has the bill already been paid? If yes, retroactive charity care
   may be available.
   → How to pursue: retroactive_charity_care.md

For each reference file in reference/:

Scaffold with relevant sections — the detailed content fills in over time:
- Title
- Purpose of this file
- Key sources (IRS regulations, HHS guidance, state laws as applicable)
- Step-by-step procedures
- Common edge cases
- Citation references

About 40-60 lines per file.

After creating all files, commit with message
"Add Charity Care Eligibility Skill with diagnostic index and 10 reference files".
```

## Done when

- `skills/charity_care_eligibility/SKILL.md` exists with frontmatter
- `00_diagnostic_index.md` has 7 diagnostic questions each with a file pointer
- 10 reference files exist with proper structure
- Git log shows the commit

## Next task

[Task 12 — Build the Cost Estimation Skill](12_skill_cost_estimation.md)
