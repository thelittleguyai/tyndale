# Task L03 — Coverage Connection: manual-upload mode

**Phase:** L2 · V1-Lite new
**Who:** Brock + Claude Code
**Estimated time:** 45 minutes
**Depends on:** L02, plus full Build Kit Task 13 (Coverage Connection & FHIR Skill)

> **AUDIT-CORRECTNESS UPDATE.** Coverage data in V1-Lite is not collected
> to save the user typing — it is the **independent basis for auditing
> both the bill and the EOB** (see the Independent Audit Doctrine in
> reference/principles.md). Tyndale computes what the user *should* owe
> from these coverage terms, then compares against what the provider
> billed and what the insurer's EOB claims. So coverage accuracy is
> load-bearing for *correctness*, not convenience. And the EOB itself is
> an audited input, never ground truth.

## What this task does

Adds a V1-Lite manual-upload mode to the existing Coverage Connection & FHIR Skill. The full Skill already has FHIR-mode reference files (scaffolded but inactive in V1-Lite). This task adds the manual-upload-mode reference files so the Skill works end-to-end without FHIR — acquiring the coverage terms that let Tyndale run its independent audit.

## Prompt to paste into Claude Code

```
The Coverage Connection & FHIR Skill (skills/coverage_connection_fhir/)
was built in full Build Kit Task 13 with FHIR-oriented reference files.
For V1-Lite, add a manual-upload mode so the Skill works without FHIR.

First read:
- skills/coverage_connection_fhir/SKILL.md
- tools/descriptions/v1_lite/upload_extract_coverage.md
- tools/descriptions/v1_lite/upload_classify_document.md
- reference/principles.md (P1 especially — make the ask trivial)

Then:

1. Update skills/coverage_connection_fhir/SKILL.md to document BOTH modes:
   - Add a section "Two modes: FHIR (full) and manual upload (V1-Lite)"
   - Explain that in V1-Lite, coverage data comes from uploaded documents
     via upload_extract_coverage, producing the same case file fields
   - Explain that the downstream logic (parsing, COB, edge cases) is
     identical regardless of source — only the acquisition differs
   - Mark the FHIR-mode sections with "(full Tyndale)" and the
     manual-mode sections with "(V1-Lite)"

2. Create new reference files in
   skills/coverage_connection_fhir/reference/ for manual mode:

   - manual_upload_flow.md — the step-by-step flow for acquiring coverage
     via upload: classify document → extract → check confidence → confirm
     low-confidence values with user (P1) → write to case file. State
     clearly that the PURPOSE of acquiring these terms is to give Tyndale
     the independent basis to audit both the bill and the EOB — not to
     read the EOB's answer back.
   - extraction_confidence_handling.md — how to handle the
     extraction_confidence field: high confidence (>0.9) assert silently;
     medium (0.7-0.9) note assumption and proceed; low (<0.7) confirm with
     user using a trivial yes/no question ("I read your deductible as
     $2,500 — is that right?"). Frame per P1. Add: any coverage term that
     FEEDS THE INDEPENDENT COMPUTATION (deductible amount + met,
     coinsurance rate, OOP max + met, network status) must be high
     confidence before Tyndale relies on it for the audit — these get
     confirmed even at medium confidence, because a wrong input corrupts
     the whole audit.
   - document_request_guidance.md — when coverage info is incomplete,
     how to ask the user for the specific missing document (insurance
     card photo, plan summary / SBC, EOB). Tell them exactly where to
     find each. PRIORITIZE getting the SBC and the insurance card for the
     COVERAGE TERMS, and the EOB as the insurer's CLAIM to be audited
     (not as the source of the right answer).
   - helping_the_user_find_coverage_info.md — for when the user does NOT
     have or cannot find the documents/values. Tyndale actively helps,
     per P1 (make the ask trivial) — it does NOT say "go figure it out."
     Concrete help paths:
       * "Your deductible and out-of-pocket max are on your insurance
         card or your Summary of Benefits and Coverage. Here's how to find
         your SBC: log into your insurer's member portal and look under
         'plan documents' or 'benefits'." (Give portal-finding guidance
         per major payer where possible.)
       * "Your amounts-met (how much of your deductible/OOP you've used
         this year) are in your member portal under 'claims' or 'spending
         summary,' or you can call the member-services number on your card
         and ask: 'How much of my deductible and out-of-pocket maximum
         have I met this year?'" (Give them the exact script — P1.)
       * "Don't have the EOB? Your insurer posts EOBs in the member
         portal, usually under 'claims.' You can also call and ask them to
         resend it."
       * If the user is uninsured or the bill is self-pay, Tyndale routes
         to the cost-estimation + charity-care paths (which need no
         insurance data) instead of stalling on coverage info.
     The principle: Tyndale treats finding the data as PART OF THE JOB it
     does for the user, not a prerequisite the user must satisfy alone.
   - value_with_incomplete_data.md — the graceful-degradation playbook
     (implements Part 3 of the Grounding & Graceful Degradation Doctrine).
     Spell out what Tyndale CAN still do at each rung:
       * Bill but no coverage terms / no EOB: still run the code-level
         checks that need no coverage data (bundling, upcoding,
         duplicates, MUE, modifier abuse, phantom charges via encounter
         verification), still benchmark the price against FAIR
         Health/Medicare, still translate the bill to plain language. State
         clearly what's deferred: "I can't yet confirm whether your
         insurer applied your benefits correctly — that needs your EOB —
         but here's what I've already found."
       * Coverage terms but no EOB: explain what they SHOULD owe given
         their benefits, so when the bill/EOB arrives they can spot a
         discrepancy themselves.
       * Just a confusing bill: translate every line item to plain
         language, flag obvious red flags, and name the one or two
         documents that unlock the full audit + exactly how to get them.
     The rule in every case: SHOW VALUE FIRST, then help the user climb to
     the next rung. Never make usefulness conditional on perfect inputs.
   - eob_is_audited_not_trusted.md — the explicit statement, for this
     Skill, of the Independent Audit Doctrine as it applies to coverage:
     the EOB is the insurer's claim about what was covered and what is
     owed. Tyndale uses the coverage terms to compute independently what
     SHOULD be owed, then treats any gap between that and the EOB as a
     candidate payer-side finding. Cross-reference
     skills/bill_error_detection/05_payer_side_errors/.

3. The existing FHIR reference files (smart_on_fhir_oauth.md,
   coverage_resource_parsing.md, etc.) stay as-is. Add a one-line note
   at the top of smart_on_fhir_oauth.md: "mode: full-only — not active
   in V1-Lite. See manual_upload_flow.md for the V1-Lite coverage path."

4. Update the SKILL.md frontmatter description to mention both modes so
   the Skill triggers correctly in V1-Lite (manual upload) and full (FHIR).

Important: the parsing reference files (coverage_resource_parsing.md,
eob_resource_parsing.md) describe how to interpret the DATA once it's in
the case file. That logic is shared — manual mode produces the same case
file fields, so those parsing files apply to both modes. Note this
explicitly in those files. AND note in eob_resource_parsing.md that
parsing the EOB means extracting the insurer's CLAIMED figures so they
can be COMPARED against Tyndale's independent computation — never adopted
as the answer.

Commit with message "Add manual-upload mode to Coverage Connection Skill for V1-Lite (audit-basis framing, find-help, graceful degradation)".
```

## Done when

- SKILL.md documents both modes clearly
- The manual-mode reference files exist: manual_upload_flow.md,
  extraction_confidence_handling.md, document_request_guidance.md,
  eob_is_audited_not_trusted.md, helping_the_user_find_coverage_info.md,
  value_with_incomplete_data.md
- The confidence-handling logic implements P1 (trivial asks) and flags
  audit-critical terms for confirmation even at medium confidence
- helping_the_user_find_coverage_info.md gives concrete find-it help with
  scripts (P1), never "go figure it out"
- value_with_incomplete_data.md spells out the degradation ladder so
  Tyndale always shows value with partial data
- The FHIR files are marked full-only but retained
- Git log shows the commit

## Next task

[Task L04 — Collapsed Lead Planner prompt](L04_collapsed_lead_planner.md)
