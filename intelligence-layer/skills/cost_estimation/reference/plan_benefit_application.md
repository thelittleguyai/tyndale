# Applying plan benefits to a raw estimate

**Purpose.** Turn a raw UCR/allowed-amount estimate into **expected member responsibility**
by applying the user's specific plan benefits. This mirrors the independent computation the
Math Person runs on a real bill.

**Inputs needed (from the case file / coverage_connection_fhir).**
- Allowed amount (estimated from UCR, adjusted toward the in-network contracted rate if known).
- Deductible: total + amount met year-to-date.
- Coinsurance percentage (member share after deductible).
- Copay (if the service is copay-based instead of coinsurance).
- Out-of-pocket maximum: total + amount met.
- Network status (in vs. out) — drives which cost-sharing tier applies.

**Sequence.**
1. Apply remaining deductible to the allowed amount (see `deductible_state_handling.md`).
2. Apply coinsurance to the post-deductible remainder, or the copay if applicable.
3. Cap total member responsibility at the remaining OOP max (see `coinsurance_oop_calculation.md`).

**Output.** A member-responsibility range (because the allowed amount is itself a range).
State which benefit values were used and their source (plan SBC / portal). Tier A on the
numbers; Tier C on the framing.
