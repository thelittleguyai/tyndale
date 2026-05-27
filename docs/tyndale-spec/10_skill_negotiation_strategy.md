# Task 10 — Build the Negotiation & Strategy Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1.5–2 hours
**Depends on:** Tasks 01–09

## What this task does

Builds the Negotiation & Strategy Skill — the Strategist subagent's playbook for picking which appeal framework applies and sequencing the steps. Includes a diagnostic index (which appeal path is right for this case?).

## Prompt to paste into Claude Code

```
Create the Negotiation & Strategy Skill in this repository.

Directory structure:

skills/negotiation_strategy/
├── SKILL.md
├── 00_diagnostic_index.md
└── frameworks/
    ├── erisa_internal_appeal.md
    ├── aca_external_review.md
    ├── nsa_open_negotiation.md
    ├── nsa_idr_process.md
    ├── state_doi_complaint.md
    ├── state_external_review.md
    ├── medicare_appeals.md
    ├── medicaid_appeals.md
    ├── direct_provider_negotiation.md
    ├── charity_care_application.md
    └── collections_dispute.md

For SKILL.md:

YAML frontmatter:
- name: negotiation_strategy
- description: "a little pushy" description. Cover: picks which appeal
  framework applies to a specific case (ERISA internal appeal vs. ACA
  external review vs. NSA open negotiation vs. NSA IDR vs. DOI complaint
  vs. direct provider negotiation vs. charity care). Sequences the steps
  for an appeal. When to use (any time a case needs strategic direction
  on what to do next). When NOT to use (bill error detection, document
  generation — those are separate Skills). ALWAYS load
  00_diagnostic_index.md first.
- version: 1.0.0

Body (under 500 lines):
- Intro: this Skill is the Strategist's playbook. It identifies which of
  the 11 frameworks applies and sequences the steps.
- Reference to reference/principles.md (especially P5: default to action,
  not options — the Strategist should propose a specific path, not a menu)
- Reference to reference/voice_tiering.md (recommendations are Tier C)
- Two-layer architecture: load diagnostic first, then the right framework
- Brief overview of when to use each of the 11 frameworks

For 00_diagnostic_index.md:

Walk through diagnostic questions to identify the right framework:

1. Is this a self-funded employer plan? → ERISA pathway
2. Is this a fully-insured commercial plan? → ACA pathway (with ERISA
   overlay for employer-sponsored)
3. Is this a Medicare plan? → Medicare appeals pathway
4. Is this a Medicaid plan? → State Medicaid appeals
5. Did the user not choose this provider (ER, anesthesia, etc.)? → NSA
6. Has the provider already been negotiated with directly? → escalate
7. Is the user uninsured/underinsured and the bill is from a nonprofit
   hospital? → Charity care pathway
8. Is the bill in collections? → Collections dispute pathway
9. Has internal appeal been exhausted? → External review pathway

For each diagnostic question, provide:
- The signal to look for
- The pointer to which framework reference file to load

For each of the 11 framework files in frameworks/:

Scaffold each with:
- Title
- "When this framework applies" section (specific situations)
- "Step-by-step sequence" section with numbered steps
- "Deadlines" section (statutory deadlines and recommended internal pacing)
- "Required documents" section
- "Typical outcomes" section (with the caveat: NEVER predict outcomes
  per Tier C rules; describe what typically happens with the
  understanding it varies)
- "Escalation paths" section (what to do if this framework doesn't resolve)
- "Citation references" section (which authorities are typically cited
  during this framework)

About 50-70 lines per framework file. The detailed content fills in over
time with the contracted attorney's input.

After creating all files, commit with message
"Add Negotiation & Strategy Skill with diagnostic index and 11 frameworks".
```

## Done when

- `skills/negotiation_strategy/SKILL.md` exists with frontmatter
- `00_diagnostic_index.md` has 9 diagnostic questions each with a framework pointer
- 11 framework files exist with the 7 sections
- Git log shows the commit

## Next task

[Task 11 — Build the Charity Care Eligibility Skill](11_skill_charity_care.md)
