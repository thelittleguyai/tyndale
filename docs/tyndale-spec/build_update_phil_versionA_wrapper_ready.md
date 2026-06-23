# Tyndale Build Update — Version A adjustments + wrapper-readiness

**To:** Phil (CTO — app + agents + current build)
**From:** Brock
**Date:** 2026-06-12
**Companion to:** CO-002 FINAL, CO-004. This translates the finalized "Version A" data
plan into concrete build adjustments, and prepares the architecture to accept a
data-access wrapper (Jonas's work) that will later bring in 1upHealth + an eligibility
vendor (Stedi or pVerify) without a rewrite.

**Two goals of this document:**
1. **Adjust the current build** to match Version A (pre-aggregator: user uploads
   benefits/EOBs; 1upHealth supplies clinical encounter when live; public + proprietary
   data layers).
2. **Prepare the seams** so the wrapper API Jonas builds can drop in 1upHealth and the
   eligibility vendor behind stable interfaces — no agent rewrites when they arrive.

Nothing here changes the doctrines, the Agent-SDK architecture, or the protected
V1-Lite launch path.

---

## Part 1 — The seam principle (read first)

Every patient-specific data point has a **pre-aggregator source** (user upload, public
data, or computed) and a **future vendor source** (1upHealth FHIR or eligibility vendor).
The agents must never call a vendor or a parser directly. They call an **interface**;
an adapter behind it decides where the data actually comes from today.

Build these interfaces now, even though several only have a "user upload" or "public
data" adapter at first. When Jonas's wrapper lands, it registers additional adapters
behind the *same* interfaces. The agents don't change.

**Four interfaces to define (the seams):**

1. **CoverageSource** — benefit design (copays, coinsurance, deductible/OOP amounts,
   tiers, plan-year boundaries, individual-vs-family structure).
   - Adapters now: `UserUploadedSBC`, `PublicQHPPlan`, `PlanLibrary`.
   - Adapters later: `OneUpHealthCoverage`, `EligibilityVendorBenefits`.
2. **AccumulatorSource** — amount spent toward deductible/OOP, as-of a date.
   - Adapters now: `EOBStatedYTD`, `ComputedFromUploadedEOBs`.
   - Adapters later: `EligibilityVendorLiveAccumulator`, `ComputedFromFHIRClaims`.
3. **ClinicalEncounterSource** — visit date, reason seen, what was done.
   - Adapter now: `UserUploadedVisitSummary`.
   - Adapter later: `OneUpHealthClinical`.
4. **ClaimsSource** — billed-to-payer line data (codes, units, charges, adjudication
   dates, network-tier markers).
   - Adapter now: `UserUploadedEOB`.
   - Adapter later: `OneUpHealthEOB`.

Each interface returns data plus **provenance** (which adapter answered) and a
**confidence/as-of** marker. The agents already consume provenance for the case file —
extend it to carry the adapter source.

---

## Part 2 — Version A build adjustments, by feature

### Bill Reconciliation

**Already in build (confirm intact):** itemized-bill upload + OCR, EOB upload, the
three-number independent audit, citation verification.

**Adjust / add:**

- **CoverageSource interface + plan library (NEW — from CO-004 §6).** Before asking the
  user to upload their benefits, check the plan library: match on (payer, group number,
  plan ID/name, plan year) from the insurance card. On a hit, *propose* the stored
  design for one-tap confirmation ("Looks like you're on Aetna Choice POS II — deductible
  $2,000, specialist copay $40 — does this match?"). On a miss, ask for the SBC. On
  confirm, increment the entry's confidence; on reject, fork a new entry. **Never apply
  a prior year's design to a current-year claim without confirmation.** Strip all user
  identifiers from stored benefit designs (plan-level data only — no PHI in the library).
- **Benefits-document capture must recognize ALL the names (NEW).** The SBC goes by many
  names; a healthcare-naive user won't know which they have. The upload flow must accept
  and show examples of: Summary of Benefits and Coverage (SBC), Schedule of Benefits,
  Summary Plan Description (SPD), Benefit Summary / Plan Summary, Certificate of Coverage
  (COC), Evidence of Coverage (EOC), Outline of Coverage, Member Benefit Booklet /
  Benefit Booklet / Member Handbook, Plan Document, Coverage Summary, "Benefits at a
  Glance." Copy pattern: "I need your plan's benefits summary — it might be called any of
  these…" with thumbnails. If the user can't find any, that's where the plan library (or
  later the eligibility vendor) rescues them — frame the dead-end as "no problem, I can
  often get this another way."
- **AccumulatorSource interface + reconstruction engine (NEW — CO-004 §5).** Deterministic
  tool (NOT model math): order plan-year EOBs by adjudication date (fall back to DOS,
  flag the assumption), accumulate per bucket (individual/family, in-network/OON, per
  embedded/aggregate structure), output as-of state with a timestamp + assumptions list.
  **When the computed path is used, require the user to confirm they've uploaded all of
  that plan year's EOBs** — incomplete history reduces confidence; say so. Cross-validate
  any multiple readings (user-stated vs. EOB-stated vs. computed); disagreement is a
  finding.
- **ClinicalEncounterSource interface (NEW seam).** Adapter now = user-uploaded
  visit summary / op report. Wire the interface now; the `OneUpHealthClinical` adapter
  registers later. The Bill Detective uses this to verify billed codes against what
  actually happened.
- **Guided flows (NEW — CO-004 §4):** sibling-claim discovery (ask about other bills from
  the same date), COB question (one plain-language question, stored), plan-effective-date
  capture, itemized-bill guidance (detect summary bills, give a request script).
- **PA status:** user-uploaded approval/denial letter; only source. Add the upload prompt.
- **Bill vs. billed-to-payer logic (CO-004 §7):** reconcile the patient bill against the
  EOB line data; mismatches (charges absent from payer submission, amounts over EOB
  patient-responsibility) are findings (balance-billing signals).

### Find a Doctor
- NPPES provider universe; sanctions (OIG LEIE + SAM.gov + state boards); network status
  by scraped directories **behind a swappable adapter** (→ 2027 Provider Directory API) +
  TiC in-network files as corroboration; CMS Care Compare for quality; provider-specific
  cost via the pricing interface. Honest confidence framing in UI; network status is not
  a guarantee.

### Cost Estimation
- Pricing interface (Medicare PFS + Hospital MRF + TiC now; Trilliant later) — already in
  CO-002. **CoverageSource + AccumulatorSource interfaces feed the patient-responsibility
  math** (same interfaces as bill reconciliation — reuse, don't duplicate). Procedure-code
  prediction from plain-language description. PA-requirement check from the policy
  pipeline. Site-of-service/facility-fee separation from MRF data. Price-changing-modifier
  risk surfaced as "confirm before you go."

### Visit Planning
- Recombines the above *before* care: predicted codes (framed as anticipation),
  CoverageSource + AccumulatorSource for cost forecast, network status of planned
  provider, PA requirements, applicable law — plus the **coding-traps collection**
  (Tyndale-proprietary, grown by the learning loop; seed from CMS guidance + public
  billing-advocacy material).

---

## Part 3 — Claude for Healthcare: what to adopt now

Tyndale's runtime already calls the Claude API through a HIPAA-eligible org with a BAA,
so the Claude-for-Healthcare capabilities are available to the runtime (the BAA covers
Enterprise + the API/Platform; it does NOT cover Console/Workbench, Cowork, or consumer
plans — keep PHI on the covered runtime path only).

**Adopt:**
- **FHIR-development Agent Skill** — adopt nearly as-is to accelerate the wrapper's FHIR
  work (coordinate with Jonas). This is the highest-value piece — it's built for exactly
  our Agent-SDK architecture.

**Evaluate (build-time savings, not new capability):**
- **CMS Coverage Database connector, ICD-10 connector, NPI connector** — these supply
  NCD/LCD, ICD-10, and NPPES, which are already in our Bucket C build plan. Decide
  per-connector: use the managed connector vs. our own ingestion. Criterion: does the
  managed connector cover what we need with less maintenance than self-built? If yes for
  a given one, swap our ingestion for it. (These don't unlock new data — they potentially
  save engineering.)

**Re-point, don't drop-in:**
- **Prior-authorization-review Skill** — Anthropic built it for the *payer/provider* side
  (proposing determinations "for the payer's review"). Tyndale is the *patient's*
  advocate — same building blocks, inverted framing. Use it as a scaffold for the
  appeals/visit-planning logic, re-pointed toward arguing *for* the patient. Do not adopt
  its determination-for-payer stance.

---

## Part 4 — What "wrapper-ready" means concretely

When Jonas's wrapper is ready, it should be able to register adapters behind the four
interfaces (Part 1) with **zero changes to agent code**. To guarantee that:

1. **Define the four interfaces now**, with the "now" adapters, even before the wrapper
   exists. Agents call interfaces, never parsers/vendors directly.
2. **Normalize at the interface boundary.** Whether data came from an upload, public file,
   plan library, or (later) a vendor, the agents see one consistent shape per interface.
3. **Provenance + as-of + confidence on every return.** Already partly built — extend to
   name the adapter source and the freshness.
4. **The eligibility interface is the AccumulatorSource + CoverageSource pair** — the
   eligibility vendor (Stedi/pVerify) registers as adapters here, NPI-gated (config flag;
   NPI from the uploaded bill or a find-a-doc selection). Build the gate as config so
   Brock can loosen it as the NPI posture is resolved.
5. **The eligibility vendor and 1upHealth are different adapters behind possibly the same
   interfaces** — e.g., both can answer CoverageSource; the adapter layer decides
   precedence (and cross-validates when both answer). Design for multiple adapters per
   interface, not one.

---

## Part 5 — What to return to Brock
Confirm: (A) the four interfaces are the right seams, or propose better ones; (B) which
Claude-for-Healthcare connectors you'd adopt vs. keep self-built, with reasoning; (C) any
place where building the interface now (before the wrapper) creates meaningful extra work
vs. value; (D) a short sequencing note for how these adjustments fold into the current
sprint structure without touching the launch path.
