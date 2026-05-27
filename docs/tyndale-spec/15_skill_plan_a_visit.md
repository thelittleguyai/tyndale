# Task 15 — Build the Plan a Visit Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** Tasks 01–14

## Prompt to paste into Claude Code

```
Create the Plan a Visit Skill in this repository.

Directory structure:

skills/plan_a_visit/
├── SKILL.md
└── reference/
    ├── prior_authorization_check.md
    ├── referral_requirement_check.md
    ├── preventive_vs_diagnostic_coding.md
    ├── pre_visit_cost_estimate.md
    ├── facility_fee_warning.md
    ├── prep_checklist.md
    └── post_visit_followup_plan.md

For SKILL.md:

YAML frontmatter:
- name: plan_a_visit
- description: "a little pushy" description. Covers pre-visit coverage
  assurance — checking prior auth requirements, referral requirements,
  prep steps, anticipated cost. When to use (user mentions an upcoming
  appointment, procedure, or visit). When NOT to use (post-visit bill
  checking — that's bill_error_detection; appointment booking — Tyndale
  doesn't book). Lead Planner calls this directly. This Skill is a
  perfect example of P2 (surface what's next) and P4 (maximize action
  per user turn) — when user mentions a visit, Tyndale runs through all
  the pre-visit checks proactively.
- version: 1.0.0

Body (under 500 lines):
- Intro: this Skill exists to prevent post-visit surprises. By doing
  pre-visit due diligence, Tyndale catches coverage problems BEFORE the
  user incurs the cost
- GROUNDING STATEMENT (per the Grounding Doctrine in
  reference/principles.md): prior-auth and referral requirements come
  from the payer_policies collection (the payer's actual rules, version-
  stamped), preventive-vs-diagnostic coding implications from the
  billing_codes collection + ACA §2713 in laws_regulations, cost from the
  cost_estimation Skill's grounded sources. Tyndale NEVER tells a user
  "you probably need prior auth" from general knowledge — it checks the
  payer's actual policy, names it, and if it can't find the policy it says
  so rather than guessing.
- Reference to colonoscopy example (P1 with the screening vs diagnostic
  CPT code) — that's exactly this Skill's job
- Workflow: when user mentions an upcoming visit, Tyndale: (1) checks
  prior auth requirements, (2) checks referral requirements, (3)
  identifies preventive vs diagnostic coding implications, (4) estimates
  cost, (5) warns about likely facility fees, (6) provides prep
  checklist, (7) plans post-visit followup

For each reference file in reference/:

About 40-60 lines per file:
- prior_authorization_check.md — querying payer policies for PA
  requirements; helping user obtain PA in advance
- referral_requirement_check.md — HMO/POS plan referral requirements
- preventive_vs_diagnostic_coding.md — the colonoscopy case generalized;
  identifying procedures where coding determines cost-share
- pre_visit_cost_estimate.md — using Cost Estimation Skill in advance
- facility_fee_warning.md — hospital-owned outpatient facilities often
  charge facility fees that surprise users; how to warn
- prep_checklist.md — procedure-specific prep (e.g., fasting before
  blood work) that affects whether the visit will be productive
- post_visit_followup_plan.md — what to do AFTER the visit — bill
  arrival timing, what to check for in the EOB, when Tyndale will
  proactively run the bill check

Commit with message "Add Plan a Visit Skill".
```

## Done when

`skills/plan_a_visit/SKILL.md` and 7 reference files exist. Git log shows the commit.

## Next task

[Task 16 — Build the Lead Planner subagent prompt](16_subagent_lead_planner.md)
