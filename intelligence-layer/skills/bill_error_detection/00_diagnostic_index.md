# Bill Error Detection — Diagnostic Index

THE SCREENING CHECKLIST. Run this first, top to bottom, on every bill + EOB. Each
check names the signals to look for and the reference file to load if it fires.
Findings are Tier A facts; legal claims are Tier B (cite); fixes are Tier C.

> Run encounter verification (0a, 0b) FIRST — before trusting that any charged
> service happened — then the provider, coverage, NSA, admin, and payer-side checks.

## Encounter verification (run FIRST)

**Check 0a: Does each charged line item correspond to a service the patient actually received?**
Look for: line items the user doesn't recognize; tests/supplies with no matching experience; services on a date the patient wasn't there.
If suspected → load `06_encounter_verification/user_confirmation_flow.md`.

**Check 0b: Does the coded complexity level match the patient's account of the visit?**
Look for: highest-complexity E/M (e.g., 99285) for a short/simple visit; time-based codes exceeding documented time.
If suspected → load `06_encounter_verification/lineitem_plain_language.md`.

## Provider billing

**Check 1: Are codes that should be bundled billed separately?**
Look for: NCCI procedure-to-procedure pairs billed on the same day without a valid modifier.
If suspected → load `01_provider_billing/bundling.md`.

**Check 2: Is the E/M level higher than documentation supports?**
Look for: level-4/5 E/M for a routine, single-problem visit.
If suspected → load `01_provider_billing/upcoding.md`.

**Check 3: Are the same services billed twice?**
Look for: identical code + date + units appearing more than once.
If suspected → load `01_provider_billing/duplicates.md`.

**Check 4: Are modifiers used incorrectly (25, 59, 51)?**
Look for: modifier 25 on every same-day E/M; modifier 59 used to bypass an NCCI edit.
If suspected → load `01_provider_billing/modifier_abuse.md`.

**Check 5: Are services billed in quantities exceeding MUE?**
Look for: unit counts above the Medically Unlikely Edit for the code.
If suspected → load `01_provider_billing/mue_violations.md`.

**Check 6: Is place of service coded correctly?**
Look for: office service billed with a facility fee; POS mismatch inflating the allowed amount.
If suspected → load `01_provider_billing/place_of_service.md`.

**Check 7: Are charges present for services not received?**
Look for: phantom line items (see also 0a).
If suspected → load `01_provider_billing/phantom_charges.md`.

## Coverage application

**Check 8: Is the deductible math correct?**
Look for: full charge applied to deductible when only a remaining balance was due.
If suspected → load `02_coverage_application/deductible_math.md`.

**Check 9: Is in-network care billed/allowed as out-of-network?**
Look for: in-network provider, out-of-network cost-sharing applied.
If suspected → load `02_coverage_application/in_out_network_errors.md`.

**Check 10: Are preventive services billed with cost-sharing?**
Look for: cost-sharing on a USPSTF A/B service or recommended immunization in-network.
If suspected → load `02_coverage_application/preventive_violations.md`.

**Check 11: Was prior authorization actually required and obtained?**
Look for: denial "no prior auth" where auth wasn't required, or was obtained.
If suspected → load `02_coverage_application/prior_auth_violations.md`.

**Check 12: For mental health / SUD, are benefits parity-compliant?**
Look for: stricter limits/cost-sharing/NQTLs on MH/SUD than on medical/surgical.
If suspected → load `02_coverage_application/parity_violations.md`.

## NSA violations

**Check 13: Is this an ER balance bill from an out-of-network ER?**
Look for: balance billed above in-network cost-sharing for emergency care.
If suspected → load `03_nsa_violations/er_balance_bills.md`.

**Check 14: Is this a surprise specialist (anesthesiology, radiology, pathology)?**
Look for: out-of-network ancillary provider at an in-network facility.
If suspected → load `03_nsa_violations/surprise_specialists.md`.

**Check 15: Is this an air-ambulance balance bill?**
Look for: out-of-network air-ambulance charge above in-network cost-sharing.
If suspected → load `03_nsa_violations/air_ambulance.md`.

**Check 16: Does the bill differ materially from the Good Faith Estimate?**
Look for: self-pay bill exceeding the GFE by $400+.
If suspected → load `03_nsa_violations/gfe_violations.md`.

## Admin errors

**Check 17: Is this bill for the wrong patient?**
Look for: name/DOB/account mismatch; services that don't match the patient.
If suspected → load `04_admin_errors/wrong_patient.md`.

**Check 18: Was this billed before insurance was given a chance to process?**
Look for: full-charge patient bill with no EOB / claim never submitted.
If suspected → load `04_admin_errors/premature_billing.md`.

**Check 19: Has the provider sent this to collections prematurely?**
Look for: collections action before the EOB posted or before required notice.
If suspected → load `04_admin_errors/premature_collections.md`.

## PAYER-SIDE errors (the EOB is audited, NOT trusted — equal weight)

**Check P1: Does the insurer's cost-sharing calculation match Tyndale's independent computation?**
Look for: a GAP between the EOB's "member responsibility" and Tyndale's figure from the coverage terms.
If suspected → load `05_payer_side_errors/cost_sharing_miscalculation.md`.

**Check P2: Did the insurer misapply coverage (wrong benefit category, wrong plan year, benefit ignored)?**
Look for: a covered benefit processed under the wrong category or not applied at all.
If suspected → load `05_payer_side_errors/coverage_misapplied.md`.

**Check P3: Was a service wrongfully denied (inconsistent with plan terms or law)?**
Look for: a denial that contradicts the SBC, plan terms, or governing law.
If suspected → load `05_payer_side_errors/wrongful_denial.md`.

**Check P4: Did the insurer process in-network care as out-of-network (or vice versa)?**
Look for: network status on the EOB inconsistent with the provider's actual status.
If suspected → load `05_payer_side_errors/network_status_error.md`.

**Check P5: Did the insurer ignore or misapply the out-of-pocket maximum?**
Look for: cost-sharing charged after the OOP max was met.
If suspected → load `05_payer_side_errors/oop_max_ignored.md`.

## Cross-cutting

**Check 20: Are charges for non-covered services included?**
Look for: services excluded by the plan. → cross-reference `payer_policies` collection for coverage.

**Check 21: Is the date of service correct on the bill?**
Look for: DOS mismatch vs. the patient's account / EOB. → general data quality.

**Check 22: Are the provider name/NPI accurate?**
Look for: wrong rendering/billing provider or NPI. → general data quality.

**Check 23: Does the allowed amount match the contracted rate?**
Look for: allowed amount above the in-network contracted rate. → load `02_coverage_application/in_out_network_errors.md`.
