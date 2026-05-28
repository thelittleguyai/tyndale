# Deductible state handling

**Purpose.** Apply the deductible correctly given how much of it the user has met.

**The three states.**
- **Unmet (met = $0):** the allowed amount applies to the deductible first (up to the full
  deductible), so the member typically pays the full allowed amount until the deductible is met.
- **Partially met:** only the **remaining** deductible applies first; the rest of the allowed
  amount flows to coinsurance. (Common error source — see
  `bill_error_detection/02_coverage_application/deductible_math.md`.)
- **Fully met:** no deductible applies; go straight to coinsurance / copay.

**Worked logic.**
- remaining_deductible = max(0, deductible_total − deductible_met)
- to_deductible = min(allowed_amount, remaining_deductible)
- post_deductible = allowed_amount − to_deductible  → goes to coinsurance

**Get the amount-met.** If unknown, help the user retrieve it (member portal "spending
summary" / call member services) — see Coverage Connection's
`helping_the_user_find_coverage_info.md`. A wrong amount-met corrupts the estimate, so confirm it.

**Output.** Always a range, since the allowed amount is a range. State the deductible
values used and their source.
