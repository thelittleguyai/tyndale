# Coinsurance and out-of-pocket-max calculation

**Purpose.** Apply the coinsurance percentage and cap member responsibility at the
out-of-pocket maximum.

**Coinsurance.**
- member_coinsurance = coinsurance_rate × post_deductible_amount
- Example: 20% coinsurance on a $1,000 post-deductible remainder → $200 member share.
- If the benefit is **copay**-based, use the flat copay instead of coinsurance for that service.

**Out-of-pocket maximum cap.**
- remaining_oop = max(0, oop_max_total − oop_met)
- total_member_responsibility = min(deductible_portion + coinsurance_portion, remaining_oop)
- Once the OOP max is reached, in-network essential benefits are covered 100% (member owes
  $0 further). Failing to cap here is a common payer error — see
  `bill_error_detection/05_payer_side_errors/oop_max_ignored.md`.

**Output.** A member-responsibility range with the OOP cap applied. State the coinsurance
rate and OOP values used and their source. Numbers Tier A; framing Tier C.
