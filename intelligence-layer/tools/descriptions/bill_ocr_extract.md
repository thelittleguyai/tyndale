# bill_ocr_extract

mode: universal

## What it does
OCRs an uploaded bill image via Azure Document Intelligence and returns the extracted text plus
structured fields (provider, dates, charges, totals, codes).

## When to use
- To turn an uploaded bill image/PDF into machine-readable text and line items before running
  the Bill Error Detection diagnostic.

## When NOT to use
- For EOBs (use `upload_extract_eob`) or coverage docs (use `upload_extract_coverage`); to
  classify a document type first (use `upload_classify_document`).

## Arguments
- `bill_image_id` (UUID, required) — the uploaded bill image in Postgres, e.g. `"img_9c…"`.

## Returns
```json
{"extracted_text":"MERCY RADIOLOGY … CPT 70553 … $1,200.00 …",
 "structured_fields":{"provider_name":"Mercy Radiology","date_of_service":"2026-03-14",
   "line_items":[{"code":"70553","description":"MRI brain w/wo contrast","charge":1200.00}],
   "total_billed":1200.00,"codes":["70553"]}}
```

## Errors and edge cases
- Low OCR confidence / illegible image → low-confidence fields flagged; ask the user for a
  clearer photo.
- Handwritten or non-standard bills → partial extraction; fall back to user confirmation.
- PHI: the bill image contains PHI; the PreToolUse hook scrubs outbound args per BAA status
  before any external call (`docs/integration-contracts.md` §2.1).

## Used by
Bill Detective.
