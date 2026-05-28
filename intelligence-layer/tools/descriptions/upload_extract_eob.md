# upload_extract_eob

mode: v1-lite

## What it does
Extracts structured EOB data from an uploaded Explanation of Benefits document into the case
file. The EOB is the insurer's CLAIM — extracted to be audited, never adopted as the answer.

## When to use
- V1-Lite, when the user has uploaded an EOB and Tyndale needs the insurer's claimed figures to
  compare against the independent computation.

## When NOT to use
- When FHIR EOBs are available (Full V1 — use `fhir_get_eobs`).
- To extract coverage terms (use `upload_extract_coverage`).

## Arguments
- `document_id` (UUID, required) — classified as `eob`.
- `case_file_id` (UUID, required).

## Returns
**Return shape is identical to `fhir_get_eobs`** — claim ID, date of service, provider, line
items (code, charge, allowed, plan paid, member responsibility), totals — PLUS
`extraction_confidence` per value and `extraction_source` ("upload"). The case-file fields
populated are the same, so downstream subagents are agnostic to data source. Example:
```json
{"claim_id":"CLM-…","date_of_service":"2026-03-14","provider":"Mercy Radiology",
 "line_items":[{"code":"70553","charge":1200,"allowed":1830,"plan_paid":1464,"member_responsibility":1200}],
 "totals":{"member_responsibility":1200},"extraction_confidence":{"line_items.0.allowed":0.9},
 "extraction_source":"upload"}
```

## Errors and edge cases
- Low-confidence values → flagged for confirmation (P1). The EOB's figures are the insurer's
  claim — Math Person computes independently and reports the gap.
- Multi-page / multi-claim EOBs; illegible uploads → request a clearer document.
- PHI: PreToolUse scrubs outbound args per BAA status (`docs/integration-contracts.md` §2.1).

## Used by
Bill Detective, Math Person.
