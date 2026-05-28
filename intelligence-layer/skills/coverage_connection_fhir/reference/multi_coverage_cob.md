# Multiple coverage & coordination of benefits (COB)

> mode: shared — the COB logic applies to both FHIR and manual modes (manual mode just acquires each plan's terms by upload).

**What this covers.** When a user has more than one insurance plan, determining primary vs.
secondary and sequencing benefits (coordination of benefits).

**Primary vs. secondary (common rules).**
- The plan where the patient is the subscriber is usually primary over a plan where they're a dependent.
- For dependent children with two parents' plans, the "birthday rule" often applies (parent
  whose birthday falls earlier in the year = primary).
- Medicare vs. commercial: depends on employer size / situation (MSP rules).

**Sequencing.**
1. Adjudicate against the **primary** plan first (compute expected member responsibility).
2. Submit the remaining balance to the **secondary**; it may cover some/all of the primary's
   member responsibility.
3. The patient's true responsibility is what remains after both.

**Audit note.** Compute independently against each plan's terms; compare to each EOB. COB
errors (wrong primary, secondary not applied) are candidate payer-side findings. Widen any
cost estimate when COB is involved.
