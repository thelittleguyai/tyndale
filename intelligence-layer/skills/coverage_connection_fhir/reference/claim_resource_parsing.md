# Claim resource parsing

> mode: full-only — not active in V1-Lite (FHIR `Claim` resources require a FHIR connection).

**What this covers.** Interpreting the FHIR `Claim` resource and distinguishing it from the
`ExplanationOfBenefit` (EOB).

**Claim vs. EOB.**
- A **Claim** is what the provider submitted to the payer (the request for payment).
- An **EOB** is the payer's adjudication of that claim (what they decided to pay / owe).
- A claim may exist before an EOB has posted — useful for the graceful-degradation path
  (you can see what was submitted before the adjudication is available).

**Fields to extract.** Claim status, submitted line items + codes, billed amounts, provider
and rendering NPI, dates of service.

**Use.** Cross-check the claim's submitted codes against the bill (provider-side checks) and
against the EOB's adjudication (payer-side checks). Status fields tell you where the claim is
in the pipeline (submitted / in process / adjudicated / denied).
