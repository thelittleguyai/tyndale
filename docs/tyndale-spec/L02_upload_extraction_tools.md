# Task L02 — Document upload & extraction tool descriptions

**Phase:** L2 · V1-Lite new
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** L01, plus full Build Kit Task 22 (tool descriptions)

## What this task does

Creates the tool descriptions for the V1-Lite document-upload path. The critical design constraint: these tools must return the **same data shape** as the FHIR tools (`fhir_get_coverage`, `fhir_get_eobs`) so the Bill Detective and Math Person subagents consume the case file identically whether the data came from an upload or a FHIR pull.

## Prompt to paste into Claude Code

```
Create V1-Lite document-upload tool descriptions in
`tools/descriptions/v1_lite/`. These tools replace the FHIR tools in
V1-Lite but produce the SAME return shapes so the subagents never know
the difference.

First, read these for the contract you must match:
- tools/descriptions/fhir_get_coverage.md
- tools/descriptions/fhir_get_eobs.md
- tools/descriptions/bill_ocr_extract.md
- collections/schemas/ (for data shapes)

Create these tool description files, each following the standard 7-section
structure (What it does / When to use / When NOT to use / Arguments /
Returns / Errors and edge cases / Used by). Add `mode: v1-lite` to each
file's header.

1. `upload_extract_coverage.md`
   - What it does: Extracts structured coverage data from an uploaded
     insurance card + plan summary document(s)
   - Returns: SAME shape as fhir_get_coverage — plan name, payer,
     subscriber, member ID, group number, effective dates, deductible
     (individual/family, met/remaining), coinsurance %, OOP max
     (met/remaining), plan type. PLUS an `extraction_confidence` field
     (0.0-1.0) per extracted value and an `extraction_source` field
     ("upload" vs "fhir" — always "upload" here).
   - When to use: V1-Lite, when a user has uploaded their insurance
     card and/or plan summary
   - When NOT to use: when FHIR coverage is available (full Tyndale)
   - Edge cases: low-confidence extraction triggers a user-confirmation
     prompt (handled by Lead Planner per P1); multi-plan households;
     illegible uploads
   - Used by: Math Person, Lead Planner

2. `upload_extract_eob.md`
   - What it does: Extracts structured EOB data from an uploaded
     Explanation of Benefits document
   - Returns: SAME shape as fhir_get_eobs — claim ID, date of service,
     provider, line items (code, charge, allowed, plan paid, member
     responsibility), totals. PLUS extraction_confidence per value and
     extraction_source.
   - Used by: Bill Detective, Math Person

3. `upload_classify_document.md`
   - What it does: Classifies an uploaded document as bill / EOB /
     insurance card / plan summary / denial letter / collections notice
     / other, so the right extraction tool runs
   - Returns: document_type (enum), confidence, suggested_next_tool
   - When to use: immediately on any upload, before extraction
   - Used by: Lead Planner

4. `upload_request_missing.md`
   - What it does: Generates a clear, specific request for a document
     the user hasn't uploaded but that's needed to proceed (per P1:
     make the ask trivial)
   - Arguments: case_file_id, missing_document_type, reason
   - Returns: a user-facing message explaining exactly what to upload
     and why, with guidance on where to find it
   - When to use: when analysis is blocked on a missing document
   - Used by: Lead Planner

IMPORTANT — the return-shape match is the whole point. Each tool's
Returns section must explicitly state: "Return shape is identical to
<fhir tool> with the addition of extraction_confidence and
extraction_source fields. The case file fields populated are the same,
so downstream subagents are agnostic to data source."

Also update MODES.md to list these four tools under mode: v1-lite.

Also add a short note to tools/descriptions/fhir_get_coverage.md and
fhir_get_eobs.md (in a new "V1-Lite note" section at the bottom):
"In V1-Lite this tool is not active. upload_extract_coverage /
upload_extract_eob produce the same return shape from uploaded
documents. When FHIR goes live, this tool is added alongside the upload
tools — the upload path remains for users who prefer it."

Commit with message "Add V1-Lite document-upload extraction tools (FHIR-shape-compatible)".
```

## Done when

- Four tool description files exist in `tools/descriptions/v1_lite/`
- Each Returns section explicitly states the FHIR-shape compatibility
- The FHIR tool descriptions have the V1-Lite note added
- MODES.md updated
- Git log shows the commit

## Next task

[Task L03 — Coverage Connection: manual mode](L03_manual_coverage_mode.md)
