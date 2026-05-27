# Task 08 — Build the Bill Error Detection Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 2–3 hours (largest Skill)
**Depends on:** Phase 1 complete (Tasks 01–07)

> **AUDIT-CORRECTNESS UPDATE (applies to both V1-Lite and full Tyndale).**
> Two additions reflect Tyndale's Independent Audit Doctrine (see
> reference/principles.md):
> 1. **Payer-side errors get equal weight to provider-side errors.** The
>    EOB is audited, not trusted. The diagnostic index must screen for
>    insurer mistakes (cost-sharing miscalculation, coverage misapplied,
>    wrongful denial, in-network processed as out-of-network) with the
>    same rigor as provider mistakes. The original categories below lean
>    provider-side; this update ensures the payer side is first-class.
> 2. **Encounter verification.** Before trusting that a charged service
>    happened, Tyndale translates each line item to plain language and has
>    the user confirm it matches their visit (V1-Lite) or checks clinical
>    data (full). A new diagnostic check and reference file cover this.

## What this task does

Builds the largest and most important Skill — Bill Error Detection. This is the Skill the Bill Detective subagent consults on every bill check. It includes a diagnostic index (the screening checklist) and reference files across error categories — provider-side, payer-side, and encounter verification.

The architecture is **two-layer**: the diagnostic index runs first to identify what kind of error might be present; only then does the agent load the specific remediation playbook.

## Prompt to paste into Claude Code

```
Create the Bill Error Detection Skill in this repository.

Directory structure to create:

skills/bill_error_detection/
├── SKILL.md
├── 00_diagnostic_index.md
├── 01_provider_billing/
│   ├── bundling.md
│   ├── upcoding.md
│   ├── duplicates.md
│   ├── modifier_abuse.md
│   ├── mue_violations.md
│   ├── place_of_service.md
│   └── phantom_charges.md
├── 02_coverage_application/
│   ├── deductible_math.md
│   ├── in_out_network_errors.md
│   ├── preventive_violations.md
│   ├── prior_auth_violations.md
│   └── parity_violations.md
├── 03_nsa_violations/
│   ├── er_balance_bills.md
│   ├── surprise_specialists.md
│   ├── air_ambulance.md
│   └── gfe_violations.md
├── 04_admin_errors/
│   ├── wrong_patient.md
│   ├── premature_billing.md
│   └── premature_collections.md
├── 05_payer_side_errors/
│   ├── cost_sharing_miscalculation.md
│   ├── coverage_misapplied.md
│   ├── wrongful_denial.md
│   ├── network_status_error.md
│   └── oop_max_ignored.md
└── 06_encounter_verification/
    ├── lineitem_plain_language.md
    └── user_confirmation_flow.md

For SKILL.md:

YAML frontmatter (top):
- name: bill_error_detection
- description: Multi-paragraph, "a little pushy" description that
  invites the Skill's use. Cover what it does (detect errors in
  medical bills across all four categories), when to use it
  (whenever a bill needs to be checked), when NOT to use it (cost
  estimation, coverage connection, appeal letter drafting — point
  to the right Skill for each). Specifically instruct: "ALWAYS load
  00_diagnostic_index.md first."
- version: 1.0.0

Body (under 500 lines):
- Brief intro explaining the two-layer architecture (diagnostic first,
  then remediation)
- Reference to reference/principles.md for the operating principles
- Reference to reference/voice_tiering.md (Tier A facts on findings;
  Tier B legal claims on NSA/ACA violations with citations)
- Reference to reference/citations.md for citation format
- A list of the 18 reference files by category, with a one-line
  description of each
- Index of the diagnostic checks (1-23, see below) with a pointer to
  which reference file each one maps to

For 00_diagnostic_index.md:

This is THE SCREENING CHECKLIST. It walks through 23 diagnostic checks
systematically. Structure each check as:

**Check {N}: {Question}**
Look for: [specific signals to look for in the bill/EOB]
If suspected → load `{path/to/file.md}` for detailed rules and citation language.

The 23 checks should cover:

Encounter verification (run FIRST — before trusting any charge, confirm the service happened):
0a. Does each charged line item correspond to a service the patient
    actually received? → 06_encounter_verification/user_confirmation_flow.md
0b. Does the coded complexity level (e.g., E/M level) match the patient's
    account of the visit? → 06_encounter_verification/lineitem_plain_language.md

Provider billing:
1. Are codes that should be bundled billed separately? → 01_provider_billing/bundling.md
2. Is the E/M level higher than documentation supports? → 01_provider_billing/upcoding.md
3. Are the same services billed twice? → 01_provider_billing/duplicates.md
4. Are modifiers used incorrectly (modifier 25, 59, 51)? → 01_provider_billing/modifier_abuse.md
5. Are services billed in quantities exceeding MUE? → 01_provider_billing/mue_violations.md
6. Is place of service coded correctly? → 01_provider_billing/place_of_service.md
7. Are charges present for services not received? → 01_provider_billing/phantom_charges.md

Coverage application:
8. Is the deductible math correct? → 02_coverage_application/deductible_math.md
9. Is the visit billed as out-of-network when it should be in-network? → 02_coverage_application/in_out_network_errors.md
10. Are preventive services billed with cost-sharing? → 02_coverage_application/preventive_violations.md
11. Was prior authorization actually required and obtained? → 02_coverage_application/prior_auth_violations.md
12. For mental health/SUD: are benefits parity-compliant? → 02_coverage_application/parity_violations.md

NSA violations:
13. Is this an ER balance bill from out-of-network ER? → 03_nsa_violations/er_balance_bills.md
14. Is this a surprise specialist (anesthesiology, radiology, pathology)? → 03_nsa_violations/surprise_specialists.md
15. Is this an air ambulance balance bill? → 03_nsa_violations/air_ambulance.md
16. Does the bill differ materially from the Good Faith Estimate? → 03_nsa_violations/gfe_violations.md

Admin errors:
17. Is this bill for the wrong patient? → 04_admin_errors/wrong_patient.md
18. Was this billed before insurance was given a chance to process? → 04_admin_errors/premature_billing.md
19. Has the provider sent this to collections prematurely? → 04_admin_errors/premature_collections.md

PAYER-SIDE errors (the EOB is audited, NOT trusted — give these equal weight):
P1. Does the insurer's cost-sharing calculation match Tyndale's independent
    computation? → 05_payer_side_errors/cost_sharing_miscalculation.md
P2. Did the insurer misapply coverage (wrong benefit category, wrong plan
    year, benefit ignored)? → 05_payer_side_errors/coverage_misapplied.md
P3. Was a service wrongfully denied (denial inconsistent with plan terms or
    law)? → 05_payer_side_errors/wrongful_denial.md
P4. Did the insurer process in-network care as out-of-network (or vice
    versa)? → 05_payer_side_errors/network_status_error.md
P5. Did the insurer ignore or misapply the out-of-pocket maximum? →
    05_payer_side_errors/oop_max_ignored.md

Cross-cutting:
20. Are charges for non-covered services included? → check payer_policies for coverage
21. Is the date of service correct on the bill? → general data quality
22. Are the provider name/NPI accurate? → general data quality
23. Does the allowed amount match the contracted rate? → 02_coverage_application/in_out_network_errors.md

For the two new categories, create reference files:

05_payer_side_errors/ (5 files) — each follows the same 7-section
structure as the other reference files (What this is, Detection signals,
Citation language, Severity, Common defenses, Required evidence,
Recommended remediation). The key framing in every one of these files:
the EOB is the insurer's CLAIM, and the detection signal is a GAP between
the insurer's stated figure/decision and Tyndale's independent
computation or the plan terms. These are the errors an ordinary person
never catches because they assume the insurer did the math right.

06_encounter_verification/ (2 files):
- lineitem_plain_language.md — how to translate a charged line item
  (code + descriptor + complexity level) into plain language the user can
  evaluate from lived experience. CRITICAL LINE: translate the FACTUAL
  meaning ("you were billed for the highest-complexity ER visit, which
  usually means a long intensive workup"), never ask for a CLINICAL
  JUDGMENT ("was it necessary?"). Include examples for common high-risk
  line items: E/M levels, time-based codes, units/quantities, add-on
  procedures, lab panels.
- user_confirmation_flow.md — the flow for asking the user to confirm
  each translated line item matches their visit, bundling the
  confirmations per P3 (one message, not a sequence), and converting a
  mismatch into a candidate phantom-charge or upcoding finding. In full
  Tyndale this step is replaced/augmented by clinical encounter data;
  note that this file's logic carries forward as the fallback and as the
  validation labels for the automated version.

For each of the 18 detailed reference files:

Don't fill them with comprehensive content yet — that comes from the
domain expert work. For now, create each file with:

- Title (the error type)
- A brief "What this is" paragraph (1–2 sentences)
- A "Detection signals" section (specific patterns to look for)
- A "Citation language" section (which authority to cite when this
  error is found, in the format from reference/citations.md — leave
  the src_id as a placeholder like `src_TBD`)
- A "Severity" section (low/medium/high — provider error vs.
  systemic billing fraud)
- A "Common defenses" section (what payers/providers typically argue;
  how to respond)
- A "Required evidence" section (what documents the user should gather)
- A "Recommended remediation" section (the typical next step; reference
  the Negotiation & Strategy Skill for full appeal sequencing)

The detailed content of each file will be filled in over time as Brock
authors them with the domain expert. For now, scaffold them with the
structure above plus enough placeholder content to make the structure
clear — about 30-50 lines per file.

Important: Every detection rule and citation framing should follow
voice tier rules from reference/voice_tiering.md. Detection findings
are Tier A facts (assert directly). Legal claims about why the error
is wrong are Tier B (confident qualifier + citation). Recommendations
for what to do about it are Tier C (frame as options with reasoning).

After creating all files, commit with message
"Add Bill Error Detection Skill with diagnostic index and 18 reference files".

Then show me the resulting tree under skills/bill_error_detection/.
```

## Done when

- `skills/bill_error_detection/SKILL.md` exists with proper YAML frontmatter
- `00_diagnostic_index.md` has the encounter-verification checks (0a, 0b) first, the provider-side checks, the coverage checks, the NSA checks, the admin checks, the five payer-side checks (P1–P5), and the cross-cutting checks — each with a file pointer
- Reference files exist in all six category subdirectories (provider billing, coverage application, NSA, admin, payer-side errors, encounter verification)
- The payer-side files frame detection as a GAP between the insurer's claim and Tyndale's independent computation
- The encounter-verification files hold the facts-not-clinical-judgment line
- Each reference file has the 7 sections (What this is, Detection signals, Citation language, Severity, Common defenses, Required evidence, Recommended remediation) where applicable
- Git log shows the commit

## Next task

[Task 09 — Build the Document Generation Skill (21 letter types)](09_skill_document_generation.md)
