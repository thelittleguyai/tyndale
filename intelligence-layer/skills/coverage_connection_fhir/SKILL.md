---
name: coverage_connection_fhir
description: |
  Acquire and interpret a user's insurance coverage data — in TWO modes. FHIR mode
  (Full V1): SMART-on-FHIR OAuth via 1upHealth to pull Coverage, ExplanationOfBenefit
  (EOB), Claim, and ClinicalNote resources. Manual-upload mode (V1-Lite): coverage
  terms come from uploaded documents (insurance card, SBC, EOB) via
  upload_extract_coverage, producing the SAME case-file fields. Use this any time
  Tyndale needs to pull, refresh, or interpret coverage data, handle multiple
  coverages / COB, or work through recent plan changes. Do NOT use it to estimate
  cost (use cost_estimation) or to find bill errors (use bill_error_detection).
  Coverage data is the INDEPENDENT BASIS for auditing both the bill and the EOB —
  not a convenience, and the EOB is audited, never trusted.
version: 1.0.0
---

# Coverage Connection & FHIR Skill

Acquires coverage data and interprets it. Two modes; identical downstream logic.

## Two modes: FHIR (full) and manual upload (V1-Lite)

- **FHIR mode (full Tyndale).** 1upHealth is the sole FHIR provider at V1. A SMART-on-FHIR
  OAuth flow pulls FHIR resources directly. See the FHIR-mode reference files (marked
  `mode: full-only`).
- **Manual-upload mode (V1-Lite).** Coverage terms come from documents the user uploads
  (insurance card, Summary of Benefits and Coverage, EOB) via `upload_extract_coverage`. See
  the manual-mode reference files.
- **Only the acquisition differs.** Both modes produce the **same case-file fields**, so all
  downstream logic (parsing, COB, edge cases) is identical regardless of source.

## OAuth flow overview (FHIR mode)

SMART-on-FHIR app-launch sequence: authorize → token → fetch resources → refresh. The actual
OAuth implementation is built by the engineering team; this Skill describes WHAT to do with
the data once retrieved. See `reference/smart_on_fhir_oauth.md`.

## Resources Tyndale pulls (FHIR mode)

`Coverage` (plan terms), `ExplanationOfBenefit` (the EOB), `Claim`, and `ClinicalNote` when
relevant. Parsing of each is in the `reference/*_resource_parsing.md` files (shared with
manual mode).

## AUDIT-BASIS STATEMENT (Independent Audit Doctrine)

The EOB / `ExplanationOfBenefit` resource Tyndale pulls is the **insurer's CLAIM**, to be
audited — not the source of truth. Even with clean FHIR data, the Math Person computes member
responsibility **independently from the Coverage resource terms first**, then compares against
the EOB. FHIR makes the data cleaner; it does NOT make the insurer's math correct. Any gap is
a candidate payer-side finding (see `bill_error_detection/05_payer_side_errors/`).

## GRACEFUL-DEGRADATION STATEMENT (Grounding & Graceful Degradation Doctrine)

FHIR pulls are not always complete — a recent visit's EOB may not have posted, a payer may
return partial resources, clinical notes may be unavailable. When data is partial, Tyndale
degrades exactly like the V1-Lite manual path: do the most you can with what you have, state
what you can't yet conclude, tell the user what's pending and when it'll likely resolve
("your insurer hasn't posted the EOB for this visit yet — I'll re-check automatically, but
here's what I can already tell you from the bill's codes"). Never dead-end the user because a
resource is missing. See `reference/partial_fhir_data.md` (FHIR) and
`reference/value_with_incomplete_data.md` (V1-Lite) — identical behavior.

## Foundation references

- [`intelligence-layer/reference/principles.md`](../../reference/principles.md) — P1 (make the ask trivial; help the user find data is part of the job).
- [`intelligence-layer/reference/voice_tiering.md`](../../reference/voice_tiering.md) · [`intelligence-layer/reference/citations.md`](../../reference/citations.md).

## Reference files

FHIR mode (full): `smart_on_fhir_oauth.md`, `claim_resource_parsing.md`, `partial_fhir_data.md`, `connection_troubleshooting.md`
Shared (both modes): `coverage_resource_parsing.md`, `eob_resource_parsing.md`, `multi_coverage_cob.md`, `recent_plan_changes.md`
Manual mode (V1-Lite): `manual_upload_flow.md`, `extraction_confidence_handling.md`, `document_request_guidance.md`, `helping_the_user_find_coverage_info.md`, `value_with_incomplete_data.md`, `eob_is_audited_not_trusted.md`
