# Tyndale Decision Log

Every locked decision from the parent build plan and the Phase 0 spec, recorded with date
and owner. This is searchable history, not a research paper — one paragraph of reasoning per
entry. New decisions append here as `DL-NN`. Status updates on the out-of-Cowork parallel
tracks (counsel, BAAs, licensing, Azure tenancy) flow through Brock and are recorded here as
they land.

---

## DL-01 — V1-Lite ships first, Full V1 immediately after
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Build and launch V1-Lite — a forward-compatible subset with a 3-agent
intelligence layer and document upload — first, then begin the Full V1 expansion immediately
on V1-Lite launch.
**Reasoning:** V1-Lite proves the core audit brain end-to-end while deferring the heavier
FHIR and letter-generation surface. Because V1-Lite's contracts (case-file schema, citation
format, voice tiering, tool return shapes) are Full V1's contracts, the upgrade is expansion,
not rewrite — and the feedback loop running from day one generates the labels that train
Full V1.
**Reversibility:** locked

## DL-02 — Single brand with beta framing
**Date:** 2026-05-27
**Decided by:** Brock (from docs, reaffirmed)
**Decision:** Ship under a single brand, "Tyndale," with explicit beta framing, rather than
splitting V1-Lite and Full V1 into separate products or brands.
**Reasoning:** One brand keeps the consumer story simple and carries V1-Lite users straight
into Full V1; beta framing sets accurate expectations during the limited-capability launch
window.
**Reversibility:** locked

## DL-03 — National launch, all 50 states
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Launch nationally across all 50 states rather than piloting in a subset.
Tier-1 commercial payers at V1-Lite: UnitedHealthcare, Anthem, Aetna, Cigna, BCBS, Humana,
Kaiser. Medicare/Medicaid deferred to Full V1.
**Reasoning:** The federal-law layer (ACA, ERISA, NSA) plus the State-Specific Rights
Addendum covers the legal surface, and the Tier-1 payers are national — so a single-state
pilot would add gating without reducing legal complexity.
**Reversibility:** locked

## DL-04 — Crisis decline with no routing of any kind, reaffirmed
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Mental-health crisis input gets a clean decline with no 988 referral and no
routing of any kind; a Haiku 4.5 classifier screens input ahead of normal processing and
triggers the decline immediately, bypassing the Lead Planner.
**Reasoning:** Tyndale is a medical-billing advocacy/reconciliation platform, not a crisis
center, and the brand claims authority only over what it itself handles. Brock reaffirmed
this deliberately; it is the most-disputed category in the design (no-988 is unusual for
consumer AI), so a single pre-launch revisit is noted, but the default stands.
**Reversibility:** locked (one pre-launch revisit noted)

## DL-05 — Non-HIPAA-covered consumer-health-app posture
**Date:** 2026-05-27
**Decided by:** Brock (pending counsel confirmation)
**Decision:** Tyndale ships as a non-HIPAA-covered consumer-health app governed by the FTC
Act, the FTC Health Breach Notification Rule, and state privacy/health-data laws — not as a
covered entity or business associate.
**Reasoning:** The user voluntarily uploads their own documents for their own benefit, which
generally keeps the app outside HIPAA coverage. Technical discipline (encryption, PHI
scrubbing, audit log, vendor BAAs) is unchanged because the data is still sensitive and state
laws (e.g., Washington MHMDA, California sensitive-PI) are stringent; only the framing
changes. Counsel must reconfirm in writing before launch, and Full V1's 1upHealth
integration triggers a HIPAA re-look.
**Reversibility:** revisable with cause (pending counsel confirmation; 1upHealth re-look)

## DL-06 — Tech stack: React Native + Expo (universal) + Next.js marketing landing
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** React Native + Expo as a universal codebase (web + iOS + Android via Expo
Router) for the product, with a small sibling Next.js project for the marketing/SEO landing.
**Reasoning:** One codebase across web and native minimizes duplicated product surface for a
small team; Next.js is kept only for the static marketing landing where SEO matters. Phil
owns the stack decision and will ramp on RN with team support.
**Reversibility:** locked

## DL-07 — Single monorepo in tyndale.git
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** All code lives in a single monorepo, `tyndale.git`, with a subtree layout
(`intelligence-layer/`, `runtime/`, `apps/*`, `packages/shared/`, `infra/`).
**Reasoning:** A monorepo is the single source of truth for V1-Lite contracts — a TypeScript
type change in `packages/shared` type-checks across mobile and web-marketing instantly, and
the runtime references the same contracts. Apps stay decoupled at deploy time even while
coupled at the contract level.
**Reversibility:** locked

## DL-08 — Walking-skeleton build sequencing
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** Build a thin end-to-end walking skeleton first, then thicken each layer;
owners (Phil/Jonas/Josh/Brock) work in parallel after Phase 1.
**Reasoning:** A thin end-to-end path surfaces integration risk early and gives every track a
real contract to build against, instead of completing layers in isolation and discovering
mismatches late.
**Reversibility:** locked

## DL-09 — Plausible for analytics; no advertising/retargeting trackers anywhere
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** Use Plausible for first-party, privacy-respecting analytics; no advertising or
retargeting trackers anywhere in the product.
**Reasoning:** A consumer-health app handling billing data cannot carry ad/retargeting
trackers without undermining its privacy posture and state-law compliance. Plausible is
cookieless (no GDPR banner needed) and sufficient for V1-Lite traffic; a pre-launch DOM audit
confirms no trackers reached health/billing pages.
**Reversibility:** locked

## DL-10 — Free-tier abuse controls: email + phone verification + Terms Section 8
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** Guard the free tier (one bill analysis) with email (via Google) + phone
verification at signup, backed by Terms Section 8's explicit prohibition on multi-account
evasion.
**Reasoning:** The free tier invites multi-account abuse; verification at signup plus
contractual suspension power is the lightest control that meaningfully raises the cost of
evasion without burdening legitimate users.
**Reversibility:** locked

## DL-11 — Security/HIPAA infrastructure built by Brock's contact, tracked outside this plan
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** The security/HIPAA spine (Presidio scrubbing, encrypted audit log, key
rotation, prompt-injection + citation hooks, crisis classifier, LiteLLM proxy hardening,
email approval gate, BAA chain) is built by Brock's contact and tracked outside Cowork's
plan; Cowork specifies integration contracts only.
**Reasoning:** The security work is specialized and runs on its own schedule. Isolating it
behind a stable interface (`docs/integration-contracts.md`) lets the rest of the team build
against contracts without owning the implementation, and keeps the sensitive spine with a
dedicated owner.
**Reversibility:** locked

## DL-12 — Apple Sign-In: fast-follow at native iOS submission, not V1-Lite web launch
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** V1-Lite web launches with Google + Email sign-in; Apple Sign-In stands up in
parallel during Phases 2–4 and ships with the native iOS App Store submission, not the
V1-Lite web launch.
**Reasoning:** Apple Sign-In is required by App Store policy for native iOS but not for the
web launch; deferring it to the iOS submission removes it from the web-launch critical path
while still landing before the native app needs it.
**Reversibility:** locked

## DL-13 — Change Order 001 (4 behavioral additions) accepted into V1-Lite
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Accept Change Order 001's four behavioral additions into V1-Lite scope: an
always-loaded behavioral core, an enumerated proactive thinking loop, lead-with-status on app
open, and a `research_log` field on the case file.
**Reasoning:** All four are additive and forward-compatible — they sharpen the "thinks five
steps ahead" promise and the audit discipline without changing contracts. The `research_log`
in particular implements the "what do I now know?" step the Lead Planner reads before
re-investigating.
**Reversibility:** locked

## DL-14 — Post-V1-Lite agent-company vision parked
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Park the "Tyndale as a small AI agent company" north-star (six agent tiers, QA
agent, Compliance Scanner); revisit after Full V1 stabilizes.
**Reasoning:** The vision is a backlog north-star, not launch-critical, and no V1-Lite work
touches it. The strongest first additions (QA agent, Compliance Scanner) are revisited only
once Full V1 is stable so they build on a settled foundation.
**Reversibility:** revisable with cause (revisit after Full V1 stabilizes)

## DL-15 — Legal entity is The Little Guy LLC d/b/a Tyndale (Utah); governing law Utah
**Date:** 2026-05-27
**Decided by:** Brock (per legal pack)
**Decision:** The operating entity is The Little Guy LLC d/b/a Tyndale (Utah-based);
governing law is Utah.
**Reasoning:** Per the legal pack. Fixes the entity and forum for the Terms, Privacy Policy,
and the binding-arbitration / class-waiver provisions.
**Reversibility:** locked

## DL-16 — Pricing locked
**Date:** 2026-05-27
**Decided by:** Brock (per legal pack)
**Decision:** $11.99/month or $100/year for unlimited use; the free tier is one bill
analysis; subscriptions cancel at the end of the current period with no prorated refunds.
**Reasoning:** Per the legal pack. A flat unlimited price keeps the consumer offer simple;
the single free analysis demonstrates value while capping abuse (see DL-10); end-of-period
cancellation with no proration is the standard subscription posture encoded in the Terms.
**Reversibility:** locked

## DL-17 — Eligibility: 18+ US-only; parent/guardian managing minor's bills permitted
**Date:** 2026-05-27
**Decided by:** Brock (per legal pack)
**Decision:** Users must be 18+ and US-only; a parent or guardian managing a minor's bills is
permitted.
**Reasoning:** Per the legal pack. Restricting to US adults matches the regulatory posture
and payer/legal coverage; the guardian carve-out covers the common case of a parent handling
a child's medical bills without opening the app to minors directly.
**Reversibility:** locked

## DL-18 — Domain tyndaleapp.net; SendGrid Email API Pro (HIPAA-eligible tier) for sends
**Date:** 2026-05-27
**Decided by:** Phil (CTO) + Brock
**Decision:** Domain is `tyndaleapp.net`; account/notification email runs on SendGrid Email
API Pro — a HIPAA-eligible tier with BAA.
**Reasoning:** Given the consumer-health-data posture, notification email must run on a
HIPAA-eligible tier; SendGrid's standard tier does not include a BAA. Phil and Brock jointly
settled the domain and the email vendor/tier.
**Reversibility:** locked

## DL-19 — Counsel engagement + dev team capacity managed outside Cowork
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Legal counsel engagement (and legal-pack review) and development-team capacity
are managed by Brock outside Cowork's scope.
**Reasoning:** These are long-lead, people-and-contracts tracks that Cowork doesn't drive.
Recording them here keeps their status visible — counsel blocks Phase 7 publication, and
capacity affects the whole schedule — while ownership stays with Brock.
**Reversibility:** locked
