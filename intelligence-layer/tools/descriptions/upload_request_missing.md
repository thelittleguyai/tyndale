# upload_request_missing

mode: v1-lite

## What it does
Generates a clear, specific, user-facing request for a document the user hasn't uploaded but
that's needed to proceed — including exactly where to find it (per P1: make the ask trivial).

## When to use
- When analysis is blocked or limited by a missing document (e.g., no EOB to audit, no SBC for
  coverage terms).

## When NOT to use
- When the document is already present; to ask for a clinical judgment (out of scope); when the
  user is uninsured/self-pay (route to cost-estimation/charity-care instead of stalling).

## Arguments
- `case_file_id` (UUID, required).
- `missing_document_type` (enum, required) — `eob | insurance_card | plan_summary | itemized_bill | …`.
- `reason` (string, required) — why it's needed, e.g. `"to confirm how the insurer applied your benefits"`.

## Returns
```json
{"message":"To check whether your insurer applied your benefits correctly, I need your EOB. Your insurer posts EOBs in the member portal under 'claims' — or call the number on your card and ask them to resend it."}
```

## Errors and edge cases
- If the user can't locate the document, follow up with the find-help guidance in the Coverage
  Connection Skill (`helping_the_user_find_coverage_info.md`) — never "go figure it out."
- Always pair the request with the value Tyndale can already deliver (graceful degradation).

## Used by
Lead Planner (V1-Lite).
