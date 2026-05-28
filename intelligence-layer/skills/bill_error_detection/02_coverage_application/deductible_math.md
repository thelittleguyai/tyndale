# Deductible math errors

**What this is.** The deductible is applied incorrectly — most often the full charge is
applied to the deductible when only a remaining balance was due, or an already-met
deductible is charged again.

**Detection signals.**
- The amount applied to deductible on the EOB exceeds the user's remaining deductible.
- Cost-sharing computed as if the deductible were unmet when the user had met part/all of it.
- Tyndale's independent computation (from coverage terms + amount-met) differs from the EOB.

**Citation language.** Tier B when the error contradicts plan terms: "Cost-sharing must
follow the plan's accumulators; the deductible applied exceeds the remaining balance under
the SBC [plan SBC / summary plan description, src_TBD]." (Often surfaces as a payer-side
finding — cross-ref `05_payer_side_errors/cost_sharing_miscalculation.md`.)

**Severity.** Medium–high (frequently large dollar impact).

**Common defenses.** Insurer cites timing of accumulator updates. Response: provide the
amount-met as of the date of service.

**Required evidence.** EOB, the SBC, and the deductible amount-met (member portal or call).

**Recommended remediation (Tier C).** Request reprocessing with the correct accumulators;
escalate via `negotiation_strategy`.
