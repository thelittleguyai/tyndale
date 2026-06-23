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
**Return shape is identical to `fhir_get_eobs`** — an `eob` object (claim ID, billed/allowed
amounts, patient responsibility, remark codes) and `raw_ocr` — PLUS an additive **`provenance`**
block (DL-69): `adapter`, `source_kind` (`user_upload` here), `as_of` (null for uploads),
`confidence` (0.0–1.0), `assumptions[]`. `provenance.adapter` names the data source
(`UserUploadedEOB` today; an fhir_get_eobs / OneUpHealth adapter later) so downstream subagents
stay source-agnostic. The case-file fields populated are the same. CO-12B adds (additively)
best-effort heuristic accumulator fields to `eob` — `adjudication_date`, `date_of_service`,
`amount_applied_to_deductible`, `amount_applied_to_oop`, `network_status`, `deductible_ytd_stated`,
`oop_ytd_stated` (low-confidence; null when not found) — which the AccumulatorSource engine sums.
Example:
```json
{"eob":{"claim_id":"CLM-…","billed_amount":1200,"allowed_amount":830,
  "patient_responsibility":370,"remark_codes":[],
  "adjudication_date":"2026-03-14","date_of_service":"2026-03-01",
  "amount_applied_to_deductible":370,"amount_applied_to_oop":370,"network_status":"in",
  "deductible_ytd_stated":null,"oop_ytd_stated":null},
 "provenance":{"adapter":"UserUploadedEOB","source_kind":"user_upload","as_of":null,
  "confidence":0.3,"assumptions":["V1-Lite OCR heuristics; figures are the insurer's claim, audited not adopted"]},
 "raw_ocr":{"…":"…"}}
```

## Errors and edge cases
- Low-confidence values → flagged for confirmation (P1). The EOB's figures are the insurer's
  claim — Math Person computes independently and reports the gap.
- Multi-page / multi-claim EOBs; illegible uploads → request a clearer document.
- PHI: PreToolUse scrubs outbound args per BAA status (`docs/integration-contracts.md` §2.1).

## Used by
Bill Detective, Math Person.
