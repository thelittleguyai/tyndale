# Tyndale — Ground-Up Out-of-Pocket Calculation

**From:** Cowork (PM/PdM)
**To:** Brock (founder)
**Date:** 2026-06-26
**Purpose:** The data Tyndale needs and the exact mathematical steps to compute a patient's true out-of-pocket (OOP) responsibility *from the ground up* — the independent "Tyndale-computed" number at the heart of the Independent Audit. This operationalizes the Math Person spec (`18_…`), which states the principle but not the algorithm. It's the content that belongs in `subagents/math_person` + `02_coverage_application/deductible_math.md`.

**The principle it serves:** Tyndale never reads the EOB's "patient responsibility" and trusts it. It rebuilds the number from the plan terms and the codes, *then* compares its figure to (a) what the provider billed and (b) what the EOB claims — and reports all three. A gap with the EOB is a payer-side finding; a gap with the bill is a provider-side finding.

---

## Part 1 — The data Tyndale needs (the inputs)

The calculation rests on four input groups. If any load-bearing input is missing or low-confidence, Tyndale flags it for a one-question confirmation (per the Math Person spec) rather than computing on a shaky number — and if the user must get it from their plan/provider, the close-the-loop rule applies.

**A. The claim/service (from the bill + EOB):**
- CPT/HCPCS procedure code(s) and diagnosis code(s)
- Date of service (drives ordering and which plan-year terms apply)
- Place of service and the rendering provider + NPI
- **Network status** of that provider for this plan (in vs out)
- **Billed charge** (provider's list price)
- **Allowed amount** (the contracted/negotiated rate) — *this, not the billed charge, is what cost-sharing is calculated on*

**B. The plan design (from the SBC / plan documents):**
- Deductible — individual and family; **embedded vs. aggregate**
- Coinsurance rate(s) (e.g., 20%), and any service-specific copays
- Out-of-pocket maximum — individual and family (embedded)
- Separate in-network vs. out-of-network deductibles/OOP maxes (usually distinct)
- Per-service treatment: subject to deductible, copay-only, preventive ($0), or non-covered
- Grandfathered status (rare; handled silently per the preventive rule)

**C. The accumulators — year-to-date (the CO-12B engine):**
- Deductible already met (per individual and family; per in/out network)
- OOP max already met (same breakdown)

**D. The patient context:**
- Which person the claim is for (matters for embedded individual caps on a family plan)
- Secondary insurance / coordination of benefits
- Plan year boundaries (deductibles/OOP reset; a January claim may sit in a different accumulator than December)
- State (for protections that change the allowed-amount basis, e.g., surprise-billing)

**E. Clinical encounter data (the reality check):**
- What the patient actually received, and the true complexity/level of the visit
- Used to verify the billed charges are real *before* the math runs on them — Tyndale never computes OOP on a phantom or upcoded charge (garbage in, garbage out)
- Source: Full V1 pulls clinical encounter records (the `ClinicalEncounterSource` interface); V1-Lite gets it by having the user confirm plain-language line items (facts about the visit, never a clinical judgment)

---

## Part 2 — The math, step by step (single claim)

**Step 0 — Establish the cost-sharing basis = the ALLOWED amount.** In-network, that's the contracted rate; the difference between billed and allowed is a contractual write-off the patient never owes (if an in-network provider bills that difference, that's balance billing — a finding). Out-of-network, it's the plan's allowed amount, or — for NSA-protected services — the in-network basis (QPA). *Auditing the allowed amount itself (is it the right contracted rate?) is a separate check via cost estimation.*

**Step 1 — Classify the service.** Preventive (in-network, non-grandfathered) → patient owes **$0; stop.** Otherwise determine whether it's copay-based, or deductible-plus-coinsurance, or non-covered.

**Step 2 — Apply the remaining deductible.**
`deductible_applied = min(allowed_amount, deductible_remaining)`
The patient pays this portion; it reduces what coinsurance applies to.

**Step 3 — Apply coinsurance to the remainder.**
`coinsurance = coinsurance_rate × (allowed_amount − deductible_applied)`
(Plus any fixed copay for the service. Whether a copay applies before the deductible is met varies by plan — read it from the SBC, don't assume.)

**Step 4 — Sum the pre-cap responsibility.**
`pre_cap = deductible_applied + coinsurance + copay`

**Step 5 — Cap at the out-of-pocket maximum.**
`patient_owes = min(pre_cap, oop_remaining)`
Anything above the remaining OOP max is the plan's to pay. Once OOP max is met, covered in-network services are 100% plan-paid for the rest of the year.

**Step 6 — Update accumulators.**
`deductible_met += deductible_applied` ; `oop_met += patient_owes`

**Step 7 — That figure is `tyndale_computed_responsibility`.** Compare it to `eob_stated_responsibility` and `billed_amount` → the three numbers and the two gaps.

**Multiple claims:** process in **date-of-service order**; accumulators carry forward claim to claim. Order matters — the same set of claims produces different per-claim splits depending on sequence, which is why the accumulator engine sorts before it sums.

### Worked example
Allowed $1,830 · deductible $2,500 with $2,100 met ($400 remaining) · coinsurance 20% · OOP max $5,000 with $2,300 met ($2,700 remaining):
- Deductible applied = min(1,830, 400) = **$400**
- Coinsurance = 20% × (1,830 − 400) = 20% × 1,430 = **$286**
- Pre-cap = 400 + 286 = **$686**
- OOP cap: min(686, 2,700) = **$686**
- **Tyndale-computed responsibility = $686.** If the EOB claims $1,200 (e.g., it applied the full $1,830 to the deductible and skipped the coinsurance split), that $514 gap is a payer-side finding.

---

## Part 3 — The rules that change the math (edge cases)

- **Allowed vs. billed:** cost-sharing is always on the allowed amount. In-network billed-minus-allowed is written off; charging it to the patient is balance billing.
- **Embedded vs. aggregate family deductible/OOP:** *embedded* = each member has their own individual deductible/OOP inside the family limit (coverage kicks in for that person once they hit the individual figure); *aggregate* = the whole family limit must be met before coinsurance for anyone. Getting this wrong is a common, expensive error.
- **ACA embedded individual OOP cap:** since 2016, on a non-grandfathered family plan no single person can be made to pay more than the individual OOP maximum (~$10,150 self-only for 2026), even if the family limit isn't met. Tyndale should enforce this cap.
- **Separate in/out-of-network accumulators:** out-of-network spending usually doesn't draw down the in-network deductible/OOP. Don't co-mingle them.
- **What counts toward the OOP max:** deductible, copays, and coinsurance for in-network covered services. **What doesn't:** premiums, balance-billed amounts, non-covered services, and (usually) out-of-network costs. Deductible *does* count toward OOP max.
- **OOP max reached** → covered in-network = $0 to the patient for the rest of the year. A charge after the max is met is a finding.
- **Non-covered services:** patient pays full and it doesn't touch the accumulators — but Tyndale first checks whether it *should* have been covered (wrongful-denial check).
- **Coordination of benefits:** primary pays first; secondary may absorb some/all of the patient responsibility. With secondary coverage, the patient's true OOP can be far below the primary EOB's stated number.
- **Low-confidence inputs:** if an extracted coverage term is shaky, flag for confirmation rather than computing on it — the independent figure is only as good as its inputs.

---

## Part 4 — How it ties back to the audit

Each computed number is grounded: allowed amounts and codes from the bill/EOB and `billing_codes`; plan terms from the SBC; accumulators from the CO-12B engine; legal overrides (preventive $0, NSA basis) from `laws_regulations`. The computed figure is Tier A (a shown, reproducible calculation); any claim that a gap *violates* a rule is Tier B (cited). Every dollar must trace to a source field or a shown step — no invented numbers.

### Two flags for you
1. The Math Person spec still lists FAIR Health tools (`cost_estimate_fair_health`) for benchmarking the allowed amount — that's stale per your data-source decision (Turquoise + Trilliant). Same update pass as the other docs.
2. The worked example in `principles.md` shows "about $560" for a similar setup, but the method gives ~$686 — looks like an imprecise illustrative number worth correcting so the doctrine doc's example is arithmetically right.
