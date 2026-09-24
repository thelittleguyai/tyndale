# Payer Portal Navigation Guide — for the 5c/5d coverage-info ladders

**From:** Cowork (PM/PdM) · **Date:** 2026-07-02 · **Status:** v1 content asset — every claim verified against the payer's own public pages on 2026-07-02 unless marked UNVERIFIED. Feeds the guided portal walkthroughs (5c combined step). **Ship rule: never print an UNVERIFIED menu path to a user — use the generic pattern instead.** Pre-launch upgrade: hands-on verification with test accounts (Phil/QA) to fill the UNVERIFIED gaps; re-verify quarterly (portals change).

## Coverage math (feeds Decision 5h)
Top-6 payers ≈ 63% of US commercial lives (UHC 16%, Elevance 12%, Aetna 12%, Cigna 9%, HCSC 8%, Kaiser 6% — AMA 2025 edition, 2024 data); the ten payers below ≈ ~70%, and the BCBS router extends reach to ~80–85%. BCBS Michigan is the one top-10 name still needing its own guide.

## The no-card registration branch (important discovery)
Some payers let a user register WITHOUT their card (SSN/last-4 + DOB): **UHC** (member ID or SSN + DOB, via HealthSafe ID), **Aetna** (ID card or SSN), **Ambetter** (member ID or last-4 SSN). But **HCSC's Blue Access for Members requires the ID number AND group number from the physical card + matching home ZIP — no SSN fallback** → no-card HCSC users can't self-register; route them to the member-services number on any bill/EOB, or HR for the SBC. The 5b identity ladder feeds this: card photo first solves registration too.

## Per-payer quick reference (verified items only)
- **UnitedHealthcare** — myuhc.com / UHC app. Signed-in section "Coverage & Benefits"; SBC/COC viewable after sign-in; "view plan spending" = deductible tracking. Register: healthsafe-id.com, member ID **or SSN** + DOB. Quirk: uhc.com/sign-in routes by plan type (employer/Medicare/Community) — start there.
- **Elevance/Anthem** — anthem.com / **Sydney Health** app. Deductible/copay status displayed on the app home ("same-page deductible status"). Register: member ID + plan ID + name + DOB. Quirk: Anthem is the Blue in only 14 states — other "Blue" cards are NOT Anthem (use BCBS router).
- **Aetna** — member.aetna.com / Aetna Health app. "Benefit balances and plan limits" on the secure site; plan documents behind login. Register: **ID card or SSN**. Quirk: separate Medicare login page catches commercial users; pharmacy may sit in CVS Caremark (unverified).
- **Cigna** — myCigna.com / myCigna app. Best-documented: dashboard = "Your Plan at a Glance" with deductible remaining, YTD in/out-of-network deductibles + OOP with progress bars. Public no-login SBC library exists for individual/family plans (cigna.com → member guide → Plan Documents); employer members use myCigna or HR.
- **Kaiser Permanente** — kp.org. Exact verified path: sign in → **Benefits → "View benefit summary" / "Coverage documents"**; tracker: **Benefits → "Track the progress of your plan"** (+ Billing → "View your out-of-pocket summary" on some plans). Quirks: region picker (8 regions, features differ); some links SSO to external TPA portals — tell users that's normal.
- **Centene/Ambetter** — member.ambetterhealth.com / Ambetter Health app. Register: member ID **or last-4 SSN**. Quirk: 29 state-branded public sites, ONE central member login — send users straight to the member portal, ignore state branding.
- **HCSC (BCBS IL/TX/OK/NM/MT)** — Blue Access for Members (state domains, e.g., bcbsil.com). "Check your deductible" in BAM. Register: **requires card** (ID + group number + ZIP match). No-card branch above.
- **Florida Blue** — floridablue.com / Florida Blue app. "View plan details like deductibles and claims" after login; public Member Forms library.
- **Highmark** — member.myhighmark.com / My Highmark app (same login web+app). Deductibles in-app; Forms Library behind login. Quirk: different legal Blues by region; My Highmark is the common front door.
- **BCBS router (all other Blues)** — ~three dozen independent Blue companies, no national login. Routing question: **"What plan name is on your card, and what are the first 3 letters of your member ID?"** (or home ZIP) → route via bcbs.com/member-services lookup. Anthem states → Anthem; IL/TX/OK/NM/MT → HCSC BAM; FL → Florida Blue; PA/DE/WV/WNY → Highmark.

## Generic fallback pattern (unlisted payers — safe to ship)
1. Check the **home dashboard** first — most portals show the deductible tracker right at login. 2. Otherwise open the menu named **"Benefits," "Coverage"/"Coverage & Benefits," or "My Plan"** — trackers appear as *plan spending / benefit balances / check your deductible / track your plan's progress*. 3. Plan documents/SBC live in the same menu under **"Plan Documents," "Coverage documents"/"Benefit summary," or "Documents & Forms"/"Forms Library."** 4. Registration prep: have the card; several payers accept SSN + DOB without it; if self-registration fails, call the member-services number on any bill/EOB — and bring the numbers back (X1).

## UNVERIFIED (do not ship; fill via hands-on pass)
Exact in-portal sub-menu labels for UHC/Anthem/Aetna/Ambetter/HCSC/Florida Blue/Highmark document lists and trackers; Cigna + Kaiser registration field requirements; HCSC/Florida Blue app names; pharmacy-portal split matrix.
