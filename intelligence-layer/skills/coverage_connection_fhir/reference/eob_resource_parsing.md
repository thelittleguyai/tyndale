# EOB resource parsing

> mode: shared — applies to both FHIR (full) and manual-upload (V1-Lite) modes. Manual mode produces the same case-file EOB fields, so this logic is identical.

**What this covers.** Parsing the FHIR `ExplanationOfBenefit` resource (or an uploaded EOB)
into the case file's EOB fields.

**CRITICAL framing — the EOB is the insurer's CLAIM, not the answer.** Parse the EOB to
extract the insurer's **claimed** figures so they can be **COMPARED** against Tyndale's
independent computation — never adopted as the answer. (See `eob_is_audited_not_trusted.md`.)

**Fields to extract (the insurer's claimed numbers).**
- Per line item: billed charge, allowed amount, plan paid, and **claimed member responsibility**.
- Adjudication / adjustment reason codes (CARC/RARC).
- Deductible/coinsurance/copay amounts the insurer says it applied.
- Network determination the insurer used.

**What to do with it.** Hold these as the EOB's CLAIM. Compute member responsibility
independently from the Coverage terms, then diff. Any gap → candidate payer-side finding
(`bill_error_detection/05_payer_side_errors/`).
