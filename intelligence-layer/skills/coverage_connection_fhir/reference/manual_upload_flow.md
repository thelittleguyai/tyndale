# Manual-upload flow (V1-Lite)

> mode: V1-Lite — the coverage-acquisition path when there is no FHIR connection.

**Purpose.** Acquire the user's coverage terms from uploaded documents so Tyndale has the
**independent basis to audit BOTH the bill AND the EOB**. The point is NOT to read the EOB's
answer back to the user — it is to compute, from the coverage terms, what the user *should*
owe, then compare.

**The flow.**
1. **Classify the document** (`upload_classify_document`) — insurance card, SBC, EOB, bill?
2. **Extract** the relevant fields (`upload_extract_coverage`) into the case-file coverage
   fields — the SAME fields FHIR mode produces, so downstream logic is identical.
3. **Check extraction confidence** per `extraction_confidence_handling.md`.
4. **Confirm low-confidence (and all audit-critical) values** with the user using a trivial
   yes/no question (P1) — never a homework assignment.
5. **Write to the case file.** Coverage terms feed the independent computation; the EOB is
   stored as the insurer's CLAIM to be audited (see `eob_is_audited_not_trusted.md`).

**If documents are missing or incomplete.** Help the user get the specific missing piece —
see `document_request_guidance.md` and `helping_the_user_find_coverage_info.md`. Meanwhile,
deliver whatever value is possible now (`value_with_incomplete_data.md`). Never stall.
