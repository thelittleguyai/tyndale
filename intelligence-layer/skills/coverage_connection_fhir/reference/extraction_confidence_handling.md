# Extraction-confidence handling (V1-Lite)

> mode: V1-Lite.

**Purpose.** Decide when to trust an extracted value silently, when to note an assumption,
and when to confirm with the user — framed per P1 (make the ask trivial).

**By the `extraction_confidence` field.**
- **High (> 0.9):** assert silently. ("You've met $2,100 of your $2,500 deductible.")
- **Medium (0.7–0.9):** note the assumption and proceed. ("I'm reading your coinsurance as
  20% — I'll use that; tell me if it's different.")
- **Low (< 0.7):** confirm with a trivial yes/no before relying on it. ("I read your
  deductible as $2,500 — is that right?")

**Audit-critical override.** Any term that FEEDS THE INDEPENDENT COMPUTATION —
deductible amount + amount met, coinsurance rate, OOP max + amount met, and network status —
must be **high confidence before Tyndale relies on it for the audit**. Confirm these with the
user **even at medium confidence**, because a wrong input corrupts the entire audit (the
three-number comparison only works if the inputs are right).

**Voice.** Confirmations are single, trivial questions (P1), bundled when there's more than
one (P3) — never a sequence of interrogating prompts.
