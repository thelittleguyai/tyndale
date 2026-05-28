# upload_classify_document

mode: v1-lite

## What it does
Classifies an uploaded document so the right extraction tool runs next: bill / EOB / insurance
card / plan summary (SBC) / denial letter / collections notice / other.

## When to use
- Immediately on ANY upload, before extraction — to route to the correct extractor.

## When NOT to use
- After the type is already known; to extract fields (use `bill_ocr_extract`,
  `upload_extract_coverage`, or `upload_extract_eob`).

## Arguments
- `document_id` (UUID, required) — the uploaded document, e.g. `"doc_4f…"`.

## Returns
```json
{"document_type":"eob","confidence":0.94,"suggested_next_tool":"upload_extract_eob"}
```
`document_type` ∈ {bill, eob, insurance_card, plan_summary, denial_letter, collections_notice, other}.

## Errors and edge cases
- Low `confidence` (<0.7) → return `"other"` and let the Lead Planner ask the user to confirm
  the document type (P1, trivial question).
- Illegible / non-document image → `document_type:"other"`, low confidence.
- PHI: the document contains PHI; the PreToolUse hook scrubs outbound args per BAA status
  (`docs/integration-contracts.md` §2.1).

## Used by
Lead Planner (V1-Lite).
