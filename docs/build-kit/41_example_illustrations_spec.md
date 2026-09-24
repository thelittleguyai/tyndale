# 41 · Example Illustrations — Generation Spec
### Cowork → Phil · 2026-09-21 · Everything needed to AI-generate the "See an example" images for the guided intake

**Decision (Brock, 9/21):** the annotated example images are AI-generated. This file gives you one ready-to-paste image prompt per document, the numbered callouts to overlay, and the legend copy (5th-grade, per A6). Sources for what each real document looks like are in `example_documents_sources_2026-09-17.md` (attached to the same message).

## Rules for every image
- **De-branded.** No insurer or hospital names, logos, or trademarks. Use "Your Insurance Company," "City Hospital," "JANE DOE," member ID `XXX-123456`, obviously fake dollar amounts.
- **No PHI, ever** — placeholders only.
- **Palette:** page background cream `#FAF7F0`; the document itself off-white with muted gray text; **callout badges teal `#3E5C57`** with white numerals; the one or two "this is the number that matters" fields highlighted money-green `#2E7D5B`.
- **Layout:** the document fills ~70% of a 4:5 portrait frame with the numbered badges pointing at fields; the legend is rendered by the app beside/below it (not baked into the image) so it can be localized and read by screen readers.
- **Legibility floor:** field labels readable on a phone at 390px wide. Prefer fewer, larger elements.
- Two documents have public federal samples that may be shown directly with no drawing: the **CMS Sample Completed SBC** and the **CMS Medicare Summary Notice sample**. Prompts are included below anyway if you prefer a consistent illustrated set.

---

## 1 · Itemized bill (vs. summary)
**Image prompt:** *Flat, clean illustration of a de-branded hospital itemized statement on a cream background. Header "City Hospital — Itemized Statement of Charges," patient "JANE DOE," account number, dates of service. A table with columns Date · Code · Description · Amount, five rows of plausible lines (e.g., 73721 MRI knee $1,240.00; 99213 office visit $210.00), a Total Charges row, and a small footer line "For your information only — a separate statement is your bill." Six teal numbered badges (1–6) pointing at: the account/visit block, the per-line date column, the 5-digit code column, the description column, the amount column, and the footer disclaimer. Muted grays, one highlighted row in soft green. No logos, no real names.*

**Legend (app-rendered):**
1. Account and visit numbers — these match your bill to your insurer's statement.
2. Each line has its own date — check for days you weren't there.
3. The 5-digit code says exactly what was billed.
4. The words should match the code. If they don't, that's a flag.
5. Each line's price. Add them up — it should match the total.
6. This line means it's the itemized list, not the bill to pay.

**Companion "summary vs. itemized" image:** *same style, two small documents side by side — left labeled "Summary" showing only three category totals (Hospital services, Lab, Pharmacy) and one grand total; right labeled "Itemized" showing many lines with codes. A teal check on the right one.*
Legend: "A summary shows only totals. An itemized bill lists every service with a code. We need the itemized one — we'll tell you how to ask for it."

## 2 · Insurance card
**Image prompt:** *Flat illustration of a generic health insurance ID card, front and back, on cream. Front: "Your Insurance Company" wordmark in plain text, "Member: JANE DOE," "Member ID: XXX-123456," "Group: 987654," "Plan: PPO," a small copay strip "Office $30 · Specialist $50 · ER $250," and "RxBIN 000000 · RxPCN XXXX." Back: "Member Services 1-800-000-0000," "Claims address." Six teal badges: member ID, group number, plan type, copay strip, Rx numbers, back-of-card phone. No logos.*

**Legend:**
1. Your member ID — it ties every statement to you. It might be a spouse's or parent's name.
2. Group number — needed when you call.
3. Plan type (PPO, HMO) — tells us if out-of-network care is covered.
4. Copays printed here are a quick check. Your plan's rulebook wins if they differ.
5. Pharmacy numbers — only for prescription bills.
6. The phone number to call for documents or to dispute a claim.

## 3 · Explanation of Benefits (EOB)
**Image prompt:** *Flat illustration of a de-branded Explanation of Benefits on cream. Top: "Explanation of Benefits — This is not a bill." Patient JANE DOE, claim number, date of service 06/14, provider "City Imaging." A table with columns: Provider charged · Allowed amount · Your deductible · Your coinsurance · Plan paid · What you owe, one or two rows of fake numbers ($2,347.18 · $1,830.00 · $400.00 · $286.00 · $1,144.00 · $686.00). Six teal badges: claim number + date, "Provider charged," "Allowed amount" (highlighted green), the deductible/coinsurance columns, "Plan paid," "What you owe." No logos.*

**Legend:**
1. Claim number and date — match these to your bill.
2. What the provider asked for.
3. **The allowed amount — the price your insurer actually agreed to. This is the number that matters.**
4. How much went to your deductible and coinsurance.
5. What your plan paid the provider.
6. What they say you owe. If your bill is higher than this, something's wrong.

## 4 · Medicare Summary Notice (MSN) — Medicare users see this instead of an EOB
**Image prompt:** *Flat illustration of a de-branded Medicare Summary Notice on cream, header "Medicare Summary Notice — This is not a bill," a "Your Deductible Status" box reading "You have met $XXX of your deductible," a claims table with Service · Amount billed · Medicare approved · Medicare paid · You may be billed. Five teal badges: the deductible-status box, service date, Medicare approved, Medicare paid, "You may be billed." No logos.* *(Or show the CMS sample directly.)*

**Legend:**
1. Your deductible status — Medicare tells you right here.
2. The date of the service.
3. What Medicare approved — the amount that counts.
4. What Medicare paid.
5. What you may be billed. Compare this to your bill.

## 5 · Summary of Benefits and Coverage (SBC) — "your plan's rulebook"
**Image prompt:** *Flat illustration of the first page of a de-branded Summary of Benefits and Coverage on cream, matching the federal layout: title "Summary of Benefits and Coverage," "Coverage Period: 01/01/2026 – 12/31/2026," "Plan Type: PPO," then the "Important Questions" table with rows "What is the overall deductible? — $2,000 / $4,000 family," "Are there other deductibles for specific services?," "What is the out-of-pocket limit? — $6,850 / $13,700," "Do you need a referral?" Six teal badges: coverage period, overall deductible row (highlighted), other deductibles row, out-of-pocket limit row (highlighted), the network vs. out-of-network columns, and a "Coverage Examples" tab at the bottom. No logos.* *(Or show the CMS Sample Completed SBC directly.)*

**Legend:**
1. The coverage period — make sure it's the right year.
2. Your deductible — what you pay before insurance starts paying.
3. Some services have their own separate deductible. Look here.
4. Your out-of-pocket limit — the most you pay in a year.
5. Two columns: in-network and out-of-network. They're different.
6. The examples page shows what a typical visit should cost on this plan.

## 6 · Your deductible on the insurer's website (portal screen)
**Image prompt:** *Flat illustration of a generic insurer member-portal screen on a phone, on cream. Header "Your plan · as of Sep 17, 2026." Two progress bars: "Deductible — $1,750 of $2,000 met · $250 remaining" and "Out-of-pocket — $2,310 of $6,850 met." A toggle "Individual / Family." A small list below titled "Claims this year" with three dated rows. Six teal badges: the "as of" date (highlighted), deductible bar, the Individual/Family toggle, the out-of-pocket bar, the claims list, and a "Plan year starts Jan 1" line. No logos.*

**Legend:**
1. **The "as of" date — this is today's number, not the number on the day of your visit.**
2. Deductible met so far — use the individual, in-network figure.
3. Individual vs. family — these are different amounts.
4. Out-of-pocket met so far — tracked separately from the deductible.
5. The claims that add up to these numbers. Screenshot this list too.
6. When your plan year starts — not always January 1.

## 7 · "All your EOBs this year" (the timeline helper)
**Image prompt:** *Flat illustration on cream: a vertical timeline from January to September with small EOB document icons at Jan 18, Feb 21, Mar 14, May 20, Jun 30 (marked "the bill we're checking" in green), Jul 18, Aug 16. April has a dashed empty slot with a teal "?" badge. Two badges: the June marker and the April gap.*

**Legend:**
1. The visit we're checking. Everything before it decides what you owed that day.
2. A gap. If you had a visit in April, we need that statement too — otherwise we'll show a range.

---

**Delivery:** seven images at 2× for retina (1560×1950 portrait, or 1560×975 for the side-by-side and the card). Store alongside the example registry keyed by ask type. Legend strings go into the copy registry as `intake.example.<doc>.<n>` so they're drift-guarded and readability-checked like everything else.
