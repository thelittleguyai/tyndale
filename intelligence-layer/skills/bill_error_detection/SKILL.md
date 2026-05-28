---
name: bill_error_detection
description: |
  Detect errors in a medical bill AND the insurer's EOB across every category
  Tyndale audits — provider-side billing errors (bundling, upcoding, duplicates,
  modifier abuse, MUE, phantom charges), coverage-application errors (deductible
  math, network status, preventive cost-sharing, prior-auth, parity), No
  Surprises Act violations, administrative errors, and PAYER-SIDE errors
  (cost-sharing miscalculation, coverage misapplied, wrongful denial, network
  mis-processing, OOP-max ignored). Use this whenever a bill or EOB needs to be
  checked for errors — it is the Bill Detective's core playbook. Do NOT use it
  to estimate what something should cost (use cost_estimation), to pull or parse
  coverage data (use coverage_connection_fhir), or to draft/sequence an appeal
  (use negotiation_strategy). ALWAYS load 00_diagnostic_index.md first, and run
  the encounter-verification checks (0a/0b) before trusting that any charged
  service even happened. The EOB is the insurer's CLAIM — audit it, never trust it.
version: 1.0.0
---

# Bill Error Detection Skill

The heart of Tyndale's value. This Skill screens a bill and EOB for errors and
points to the remediation playbook for each.

## Two-layer architecture

1. **Diagnostic first.** ALWAYS load [`00_diagnostic_index.md`](00_diagnostic_index.md)
   and run its screening checklist (23 checks + encounter verification 0a/0b). The
   diagnostic identifies *what kind* of error may be present.
2. **Remediation second.** Only after a check fires do you load the specific
   reference file for that error category — for detailed detection rules, citation
   language, defenses, required evidence, and the recommended next step.

## Operating rules (foundation references)

- Principles: [`intelligence-layer/reference/principles.md`](../../reference/principles.md)
  — especially the **Independent Audit Doctrine** (audit both the bill and the EOB;
  compute the third independent number) and the **Grounding & Graceful Degradation
  Doctrine** (do the most you can with what you have).
- Voice tiering: [`intelligence-layer/reference/voice_tiering.md`](../../reference/voice_tiering.md)
  — **detection findings are Tier A** (assert facts directly); **legal claims about
  why an error is wrong are Tier B** (confident qualifier + inline citation);
  **recommendations are Tier C** (reasoning, not outcome predictions).
- Citations: [`intelligence-layer/reference/citations.md`](../../reference/citations.md)
  — every Tier B legal claim carries `[authority §section, src_id]`.

## The Independent Audit Doctrine in this Skill

Payer-side errors get **equal weight** to provider-side errors. The EOB is the
insurer's claim about what is owed; the detection signal for a payer-side error is a
**gap** between the insurer's stated figure/decision and Tyndale's independent
computation (from the coverage terms) or the plan terms and law. These are the
errors an ordinary person never catches because they assume the insurer did the math
right. Tyndale does not.

## Reference files by category

**01_provider_billing/** (provider-side coding/billing errors)
- `bundling.md` — separately billing codes that should be bundled (NCCI PTP)
- `upcoding.md` — E/M or complexity level higher than documentation supports
- `duplicates.md` — the same service billed more than once
- `modifier_abuse.md` — misuse of modifiers 25, 59, 51
- `mue_violations.md` — units exceeding Medically Unlikely Edits
- `place_of_service.md` — wrong place-of-service code / facility fee
- `phantom_charges.md` — charges for services never rendered

**02_coverage_application/** (how benefits were applied)
- `deductible_math.md` — incorrect deductible application
- `in_out_network_errors.md` — in-network care billed/allowed as out-of-network
- `preventive_violations.md` — ACA preventive services billed with cost-sharing
- `prior_auth_violations.md` — prior-auth claimed required when it wasn't (or was obtained)
- `parity_violations.md` — MH/SUD benefits more restrictive than medical/surgical

**03_nsa_violations/** (No Surprises Act)
- `er_balance_bills.md` — out-of-network ER balance bill
- `surprise_specialists.md` — out-of-network ancillary at in-network facility
- `air_ambulance.md` — air-ambulance balance bill
- `gfe_violations.md` — bill materially exceeds the Good Faith Estimate

**04_admin_errors/**
- `wrong_patient.md` — bill belongs to a different patient
- `premature_billing.md` — billed before insurance was allowed to process
- `premature_collections.md` — sent to collections before required notice/efforts

**05_payer_side_errors/** (the EOB audited, not trusted)
- `cost_sharing_miscalculation.md` — insurer's cost-sharing ≠ Tyndale's computation
- `coverage_misapplied.md` — wrong benefit category / plan year / benefit ignored
- `wrongful_denial.md` — denial inconsistent with plan terms or law
- `network_status_error.md` — in-network processed as out-of-network (or vice versa)
- `oop_max_ignored.md` — out-of-pocket maximum ignored or misapplied

**06_encounter_verification/** (did the service happen at all?)
- `lineitem_plain_language.md` — translate each line item to plain language (facts, not clinical judgment)
- `user_confirmation_flow.md` — confirm line items match the visit; convert mismatches to findings

## Diagnostic check → reference file map

See `00_diagnostic_index.md` for the full screening logic. Summary:

| Check | Maps to |
|---|---|
| 0a, 0b encounter verification (run FIRST) | `06_encounter_verification/` |
| 1–7 provider billing | `01_provider_billing/` |
| 8–12 coverage application | `02_coverage_application/` |
| 13–16 NSA violations | `03_nsa_violations/` |
| 17–19 admin errors | `04_admin_errors/` |
| P1–P5 payer-side errors | `05_payer_side_errors/` |
| 20–23 cross-cutting (coverage, data quality, allowed-amount) | `02_coverage_application/`, payer_policies, data checks |
