# Tyndale V1-Lite — Build Plan for Brock's Approval

**Prepared by:** Cowork (PM/PdM)
**To:** Brock, via Phil (CTO)
**Date:** May 27, 2026
**Status:** Revised after Brock's first-round feedback. Pending one open question (Apple Sign-In timing) and explicit approval to start Phase 0.

This document folds in everything from the 47-file intelligence-layer source folder, the 7-file Additional Files folder (legal pack + developer/cowork notes + Change Order 001 + the parked post-V1-Lite vision), Phil's tactical decisions (stack, repo, analytics, security/HIPAA owner), and Brock's confirmed decisions (national launch, crisis-decline reaffirmed, counsel/dev capacity handled outside Cowork's scope, security/HIPAA infrastructure built by Brock's contact and tracked outside this plan).

---

## Executive summary

- Tyndale ships as a non-HIPAA-covered consumer-health app under FTC + state health-data laws. Technical discipline (encryption, scrubbing, audit log, vendor BAAs) is unchanged; the framing updates. Counsel reconfirmation handled by Brock outside this plan.
- V1-Lite ships first; Full V1 build immediately after. V1-Lite is a forward-compatible subset of Full V1.
- **Launch geography: national, all 50 states.** State-Specific Rights Addendum covers CA, VA, CO, CT, UT, TX, OR, MT, WA, NV plus the other comprehensive-privacy-law states.
- Tech stack: React Native + Expo (universal — web + iOS + Android from one codebase) + Next.js for marketing landing. Single monorepo in `tyndale.git` (currently empty). Walking-skeleton sequencing.
- **Security/HIPAA infrastructure is built by Brock's contact and tracked outside this plan.** Cowork specifies the interface contracts (hook signatures, audit-log payload shape, case-file schema, de-identification handoff); the security expert implements against them.
- Change Order 001 (four behavioral additions) is in scope. Post-V1-Lite vision is parked.
- ~18 weeks from kickoff to V1-Lite launch with parallel tracks. Full V1 work begins immediately after V1-Lite ships.

The rest of this document is structured per Brock's command: (A) understanding, (B) clarifying questions, (C) open decisions with recommendations, (D) proposed phased build plan.

---

## (A) My understanding

### What Tyndale is

Tyndale is an AI medical-billing advocate. A user gets a confusing bill, a denial, or a stack of EOBs they can't make sense of. Tyndale opens a case file, treats both the provider's bill *and* the insurer's EOB as **claims to be audited** — never as truth — and independently computes what the user should owe from their real coverage terms, the codes, the rules, and the law. Three numbers, always: what was billed, what the EOB says, what Tyndale computes. Gaps on the payer side and the provider side both get pursued. This is the **Independent Audit Doctrine** — the core promise, and what makes Tyndale different from a chatbot reading the EOB back.

Layered above that: the **Grounding & Graceful Degradation Doctrine** — every factual, legal, coverage, or pricing claim is grounded in a real retrieved source (CPT/HCPCS/ICD-10 catalogs, NCCI/MUE tables, statutes, payer policies, the user's own documents), never the model's memory. Incomplete data narrows the answer but never dead-ends; helping the user find missing pieces is part of the job.

Six interaction principles (P1–P6) operationalize "thinks five steps ahead": anticipate before asking, make the ask trivial, surface what's next, bundle questions, maximize action per turn, default to action not options, chain tools internally. A three-tier voice — Tier A facts asserted plainly, Tier B legal claims with confident qualifier + inline citation, Tier C strategic recommendations with reasoning and no outcome predictions — keeps the model honest. Five out-of-scope categories get clean declines with no routing. The mental-health crisis decline (no 988 referral, no routing of any kind) is reaffirmed by Brock: Tyndale is a medical-billing advocacy and reconciliation platform, not a crisis center, and provides no guidance or direction on crisis management.

### Architecture

Lead Planner (Sonnet 4.6) is the coordinator. Behind it run five specialists in isolated context: Bill Detective (Sonnet), Math Person (Sonnet), Legal Researcher (Sonnet), Strategist (Opus 4.7), Code Validator (Haiku 4.5). They consult eight Skills (filesystem-based playbooks with diagnostic indexes for Bill Error Detection, Negotiation & Strategy, Charity Care) and four Qdrant collections (`billing_codes`, `error_detection_rules`, `laws_regulations`, `payer_policies`). NCCI and MUE tables live in Postgres, not Qdrant. Claude Agent SDK hooks (UserPromptSubmit, PreToolUse, PostToolUse, Stop) enforce PHI scrubbing, prompt-injection scanning, citation Layer 2 resolution, and audit logging. LiteLLM proxy is the single credential broker, Claude-only fallback (Anthropic direct → Bedrock → Azure Foundry → maintenance mode). Self-hosted Qdrant inside an Azure VPC. No public ingress on any of it.

### Regulatory posture (from the legal pack)

Tyndale ships as a **non-HIPAA-covered consumer-health app**, not as a covered entity or business associate — the user voluntarily uploads their own documents for their own benefit. Governing framework: the FTC Act, the FTC Health Breach Notification Rule, and state privacy/health-data laws (especially Washington's My Health My Data Act, California's sensitive-PI rules, and the comprehensive-privacy-law states). Technical discipline doesn't change — encryption, PHI scrubbing, audit log, vendor agreements with AI providers, BAA-style contracts — because the data is still sensitive and state laws are stringent. What changes is the framing: the doctrine reads "FTC + state health-data laws + vendor contracts from day one," not "HIPAA-mandated."

Counsel must reconfirm this posture in writing before launch, and Full V1's 1upHealth integration triggers a HIPAA re-look (patient-directed API access usually keeps an app outside HIPAA, but contract structure can shift it). Legal pack (Terms, Privacy Policy, Improvement Consent, State-Specific Rights Addendum) is launch-candidate but needs attorney sign-off, especially Sections 12–14 of Terms (arbitration, class waiver, liability) and the state-specific addendum.

### V1-Lite vs Full V1

Same brain, different input path.

- **Full V1** (target): 6 agents, FHIR via 1upHealth pulls coverage + EOBs + clinical notes automatically, drafts and sends all 21 letter types on user approval.
- **V1-Lite** (what we build first): 3 agents — Lead Planner + Bill Detective + Math Person. Legal Researcher's and Strategist's logic is *folded into* the Lead Planner; Code Validator is deferred. User uploads bills/EOBs/insurance card/plan summary. Azure Document Intelligence OCRs them. Same case-file schema, same citation format, same voice tiering, same tool *return shapes* (the `upload_extract_*` tools match the FHIR tools' return shapes, so subagents are source-agnostic). No automated letter generation — Tyndale gives the user a scripted phone call or letter to handle themselves. Encounter verification by translating each line item into plain language and asking the user to confirm what happened (never clinical judgment). Plus a feedback loop with two-consent model + mandatory de-identification so V1-Lite generates the labels that train Full V1.

The upgrade to Full V1 is **expansion, not rewrite**. Forward-compatibility is the rule. V1-Lite contracts are Full V1's contracts.

### Change Order 001 is in scope (newly approved)

Four additive, forward-compatible items the build incorporates:

1. **Always-loaded behavioral core** — identity, P1–P6, the two doctrines, a silent case-intake checklist, the proactive thinking loop, "always do" rules, the confidence/escalation protocol, and a growing `worked_examples` reference file. Assembled and injected in full at every session/Lead-Planner invocation. Never retrieval-dependent. Lives in the 1-hour cache tier per the prompt-caching spec.
2. **Enumerated proactive thinking loop** before every response: what do I know / what's missing / what hasn't the user asked / deadlines / give a specific next action right now / grounding source / single most important thing for the user.
3. **Lead-with-status on app open.** Returning users see "here's where your open issues stand," driven by loaded case state. No open cases → warm brief prompt.
4. **`research_log` field on the case file** — `{timestamp, topic, what_was_checked, result_summary, finding_id}`. Lead Planner writes as it investigates and reads before re-investigating.

### Post-V1-Lite vision is parked

A "Tyndale as a small AI agent company" north-star with six agent tiers exists in the backlog. Strongest first additions after V1-Lite stabilizes: a QA agent (sampled real-time review with hold-for-approval gate) and a Compliance Scanner. No V1-Lite work touches this.

### Locked decisions I will not relitigate

3-agent V1-Lite intelligence layer. All four collections in V1-Lite. Letter generation deferred to Full V1. Two-consent feedback loop with mandatory de-identification. Upload path stays after FHIR ships. Pricing: $11.99/mo or $100/yr unlimited, cancel-at-end-of-period, no prorated refunds; free tier = one bill analysis. Claude-only routing for user-facing reasoning. Self-hosted Qdrant in Azure VPC. Manual human review of every appeal letter at V1. Single brand with beta framing. Entity: The Little Guy LLC d/b/a Tyndale, Utah-based. 18+ US-only, parent/guardian managing minor's bills allowed. Binding arbitration with 30-day opt-out, class-action waiver. Plausible for analytics; no advertising/retargeting trackers anywhere. National launch (all 50 states). Crisis decline with no routing of any kind, reaffirmed.

If anything above is wrong, correct it before we proceed.

---

## (B) Clarifying questions still needing answers

Bundled and reduced after Brock's two rounds of feedback. One sanity-check item remains; no blocking questions.

1. **Behavioral-core token budget confirmation** (FYI, not blocking). Change Order 001 item 1 requires the behavioral core loaded in full every session. Cowork estimates 4,000–6,000 tokens for the non-negotiable portion (identity + P1–P6 + doctrines + thinking loop + confidence protocol). Comfortably within the 80K-per-subagent budget, fits in 1-hour cache tier. Will validate empirically in Phase 1 when the assembled core is written.

Items resolved across Brock's two rounds:

- Apple Sign-In timing → **fast-follow**: Google + Email at V1-Lite web launch; Apple Sign-In stands up in parallel during Phases 2–4 and ships with the native iOS App Store submission.
- Counsel engagement → Brock handles outside Cowork's scope.
- AMA CPT + FAIR Health licensing → Brock working on; building proceeds in the meantime (Phases 1–4 don't depend on them; Phase 5 does).
- BAA chain status → Brock's contact handles security/HIPAA, including BAA execution.
- Security/HIPAA owner identity → contact handled by Brock; integration contracts are Cowork's only touchpoint.
- Launch geography → national, all 50 states.
- Dev team capacity → Brock confirms.
- Crisis-decline policy → reaffirmed (no routing of any kind).

---

## (C) Open decisions — status and recommendations

### Settled

- **C-1 Tech stack:** React Native + Expo (universal codebase, web + iOS + Android from one repo via Expo Router). Marketing landing as a tiny sibling Next.js project for SEO. Phil will ramp on RN with team support. *Locked by Phil (CTO).*
- **C-2 Repo structure:** Single monorepo in `tyndale.git`. Subtree layout in Phase 0. *Locked by Phil.*
- **C-3 Build sequencing:** Walking skeleton — thin end-to-end first, then thicken each layer. Phil/Jonas/Josh/Brock work in parallel after Phase 1. *Locked by Phil.*
- **C-4 Free-tier abuse:** Email (via Google) + phone verification at signup, backed by Terms Section 8 (explicit prohibition on multi-account evasion). *Locked by Phil.*
- **C-5 Launch geography:** **National launch, all 50 states.** Tier-1 payers at V1-Lite: UnitedHealthcare, Anthem, Aetna, Cigna, BCBS, Humana, Kaiser. Medicare/Medicaid deferred to Full V1. *Locked by Brock.*
- **C-6 Crisis-decline policy:** Reaffirmed — clean decline, no routing of any kind. Tyndale is a medical-billing advocacy/reconciliation platform, not a crisis center. *Locked by Brock.*
- **C-9 Analytics:** Plausible at launch. *Locked by Phil.*
- **Security/HIPAA infrastructure:** Tracked outside this plan. Brock's contact builds Presidio scrubbing + benchmark, encrypted audit log + AES-GCM key rotation in Azure Key Vault, UserPromptSubmit prompt-injection hook, Stop hook citation Layer 2 resolution, LiteLLM proxy hardening, crisis classifier (Haiku 4.5), email approval gate, and the BAA chain. Cowork specifies interface contracts only. *Locked by Brock.*
- **C-10 HIPAA-posture confirmation:** Brock handles counsel reconfirmation outside this plan. Build kit's technical discipline ships verbatim; only the framing updates.
- **C-11 Change Order 001:** Approved in the doc itself. Folded into the plan below.
- **C-12 Post-V1-Lite vision:** Parked. Full V1 work begins immediately after V1-Lite ships, per Brock.
- **C-13 Sequencing relative to Full V1:** V1-Lite first, Full V1 build starts immediately after V1-Lite launch. *Locked by Brock.*

### Settled (continued)

- **Apple Sign-In timing:** **Fast-follow.** V1-Lite web launches with Google + Email. Apple Sign-In stands up during Phases 2–4 and ships with the native iOS App Store submission. *Locked by Brock.*

### Pending — Brock's call

- **AMA CPT + FAIR Health licensing.** Brock in progress. Building proceeds without them in Phases 1–4. Required for Phase 5 (`billing_codes` ingestion and Cost Estimation accuracy).
- **Dashboard scope per screenshots.** The screenshots show a substantially broader logged-in view than L08's upload-centric spec (coverage tiles, OOP-max progress, copay tiles, Amount Saved YTD, four Skill quick-action tiles, Chat CTA). Cowork is treating screenshots as authoritative — confirm.

### Sub-decisions auto-applied unless flagged

- **C-8a Dashboard scope:** Per screenshots (broader than L08). Confirm above.
- **C-8d SendGrid healthcare tier:** Brock's contact owns vendor selection; flag is that account/notification email must run on a HIPAA-eligible tier (SendGrid Email API Pro or equivalent) given the consumer-health-data posture.

---

## (D) Proposed phased V1-Lite build plan — for approval

Eighteen weeks from kickoff to V1-Lite launch with parallel tracks. Adjust to actual hours/availability. Phases gate on the previous phase's exit criteria; within a phase, owners work concurrently.

### Phase 0 — Lock decisions + integration contracts + start build foundations (1 week)

**Owners:** Brock + Phil (CTO).
**No production code yet — interface specifications and scaffolds only.**

Cowork's Phase 0 deliverables:

- Confirm dashboard scope per screenshots
- Document the integration contracts the rest of the build needs to know about the security/HIPAA infrastructure (hook signatures, audit-log payload shape, case-file schema fields, de-identification handoff format). These become the spec the security expert builds against and that Jonas/Phil/Josh build with.
- Phil scaffolds the monorepo layout (`intelligence-layer/`, `runtime/`, `apps/mobile/`, `apps/web-marketing/`, `infra/`, `packages/shared/`) without committing production code
- Plausible account stood up

Tracked outside Cowork (Brock + contacts):
- Counsel engagement and legal-pack review
- AMA CPT + FAIR Health procurement (non-blocking for Phases 1–4)
- All nine V1-launch-critical BAAs (security/HIPAA contact owns)
- Azure tenancy provisioning
- Apple Developer enrollment (parallel during Phases 2–4 for the iOS App Store submission after V1-Lite web launch)

**Exit criteria:** Brock-approved plan, monorepo layout designed, integration contracts documented, dashboard scope confirmed. Brock confirms his out-of-plan items (counsel, BAAs, Azure tenancy, licensing) are progressing in parallel.

### Phase 1 — Foundations (3 weeks, all tracks start)

**Brock track (Claude Code, intelligence-layer authoring):**
Build kit Tasks 01–07 — repo init, principles (with Change Order 001 always-loaded behavioral core + enumerated thinking loop folded in), voice tiering, refusal templates, citations, glossary, discipline rules. Scaffold the `worked_examples.md` file.

**Phil track (web/mobile app):**
Monorepo skeleton (`tyndale.git`): `intelligence-layer/`, `runtime/`, `apps/mobile/` (Expo), `apps/web-marketing/` (Next.js), `infra/` (Terraform), `packages/shared/` (TS types). Expo project init. Design system encoding the dark dashboard + cream-light marketing palette per screenshots. Marketing landing page (Next.js, signed out, Google + Email sign-up CTA). "SCAFFOLD — not for real PHI" banner. Plausible wired up.

**Jonas track (runtime skeleton):**
FastAPI scaffold. Postgres schemas — case files (with `research_log` field per Change Order 001), audit log placeholder, findings, deadlines, user accounts. Health/readiness routes. LiteLLM proxy skeleton (real hardening comes in Phase 4).

**Josh track (knowledge layer):**
Self-hosted Qdrant in Azure VPC. Four empty collections with metadata schemas locked. Embedding client setup. No data yet.

**Phil ramp-up (parallel):** Phil works through Expo Router docs, RN-on-web patterns, and Expo's universal-app examples. Pair with senior engineer if available.

**Exit criteria:** Foundation files committed. Monorepo structure live. Expo app + Next.js marketing app both boot. FastAPI returns health. Qdrant deployed and queryable. Pre-launch checklist starts populating.

### Phase 2 — V1-Lite Skills and subagents (3 weeks)

**Brock:**
V1-Lite tasks L01–L04 + reused build kit tasks 08 (Bill Error Detection Skill, full with payer-side errors + encounter verification), 12 (Cost Estimation), 13 (Coverage Connection — manual mode + audit-basis framing), 17 (Bill Detective), 18 (Math Person with three-number audit), L04 (V1-Lite collapsed Lead Planner — with Change Order 001 thinking loop + lead-with-status behavior + worked-examples library reference). Tools descriptions for the V1-Lite subset (L02 upload-extract tools + reused subset from Task 22).

**Jonas + security/HIPAA owner (Brock's friend):**
Claude Agent SDK integration. Wire collapsed Lead Planner + Bill Detective + Math Person against the prompts Brock is authoring. Tool implementations (subset): `pg_case_file_get`, `pg_upsert_finding`, `pg_deadline_upsert`, `qdrant_search_*`, `upload_extract_coverage`, `upload_extract_eob`, `bill_ocr_extract` via Azure Document Intelligence. PreToolUse hook skeleton — security owner takes lead on Presidio integration; Jonas wires the hook lifecycle.

**Josh:**
Begin Qdrant ingestion with fixtures (Task 25 test fixtures). Embedding model selection prep — voyage-context-3 vs voyage-3-large NDCG benchmark on a curated 100-query legal set (per the locked ship gate). Standup Braintrust dev account; eval scaffolding.

**Phil:**
Google + Email sign-up flow (Auth.js v5 or Expo equivalent). Account creation with phone verification (Twilio). Logged-in dashboard scaffold per screenshots: deductible/OOP-max progress tiles, copay tiles, Amount Saved YTD card, four Skill quick-action tiles (Check a Bill, Plan a Visit, Find a Doctor, Estimate Costs), Chat CTA. Mocked data. Settings screen with the improvement-consent toggle (off by default per legal pack).

**Exit criteria:** Bill Error Detection Skill complete. Lead Planner + Bill Detective + Math Person prompts complete. V1-Lite-subset tools implemented. Phil's dashboard renders end-to-end with mocked data. Phil and Jonas have a contract specification for the API.

### Phase 3 — Walking skeleton wire-up (2 weeks)

End-to-end MRI scenario from the docs (`how_tyndale_works_reference.md`) runs through real Claude calls. Bill Detective + Math Person spawn from Lead Planner, write findings to case file, Lead Planner composes a Tier A/B/C response with three-number audit display. Upload flow runs Document Intelligence OCR. Low-confidence value-confirmation UI works (P1 in action). Encounter verification UI works with line-item plain-language translation. Three-number audit display visible in app. The "scripted next action" recommendation (V1-Lite deferral of letter generation) renders correctly.

**Exit criteria:** A real bill flows in, real subagents process it, real findings appear in the dashboard. End-to-end demo recorded.

### Phase 4 — Feedback loop, Stripe, and integration with security spine (3 weeks)

Security/HIPAA spine — dual-stream logging, Presidio scrubbing, encrypted audit log, key rotation, UserPromptSubmit + Stop hooks, crisis classifier, email approval gate, LiteLLM proxy hardening — is built by Brock's contact on a parallel track that Cowork does not track in this plan. The work below assumes those components land on a coordinated schedule and integrates against the contracts specified in Phase 0.

**Brock + Phil:**
V1-Lite tasks L05 (feedback capture schema), L06 (de-identify + promote pipeline — feedback side of the handoff to the security spine's Presidio pipeline), L07 (encounter verification fully wired). Phil builds the feedback UI: thumbs up/down + structured-reason picker, outcome follow-up, value-confirmation prompts.

**Jonas:**
Stripe integration ($11.99/mo, $100/yr unlimited). Postgres optimistic locking. Feedback-loop data pipeline (capture → triage queue → de-identification handoff to security spine). Wire hook lifecycle integration points so the security spine's hook implementations slot in cleanly.

**Exit criteria:** Feedback loop runs end-to-end with synthetic data and hands off correctly to the security spine's de-identification pipeline. Stripe in test mode. Hook integration points wired to spec.

### Phase 5 — Knowledge layer + remaining work (3 weeks)

**Josh:**
Run real ingestion for `billing_codes` (with AMA CPT license now in hand), `error_detection_rules` (free CMS NCCI/MUE narrative + ACA §2713 preventive list), `laws_regulations` (free, eCFR + state legislative scrapes), `payer_policies` (free CMS LCDs/NCDs + curated Tier-1 commercial). NCCI and MUE tables loaded into Postgres separately. Embedding NDCG benchmark complete (lock voyage-context-3 vs voyage-3-large for laws_regulations).

**Brock:**
Find a Doctor and Plan a Visit Skills if V1-Lite scope includes them (optional per L02 build kit). Status-forward app-open behavior fully wired in Lead Planner. Worked-examples library seeded with 5–10 initial examples drawn from the acceptance narrative.

**Phil:**
Encounter verification UI complete. Case tracker view (open issues + deadlines, surfacing per P2). Mobile-specific polish: Expo Router file structure stabilized, native camera flow on iOS/Android, push notifications via Expo's service.

**Exit criteria:** Real knowledge data live in Qdrant. Embedding benchmark passes ship gate. Case tracker and encounter verification both functional.

### Phase 6 — Eval suite and ship gates (3 weeks)

**All:**
Braintrust integration with GitHub Actions (per-PR smoke evals). Arize Phoenix self-hosted (production trace export). ~200–400 golden examples authored (subset of full V1 target; feedback loop grows them post-launch). Synthetic generation per Tasks 28–29 (Opus 4.7 conditioned on failure-mode taxonomies). LLM judge (Opus 4.7) calibrated against golden set; Cohen's κ ≥ 0.6 confirmed. Run all 7 ship gates against the V1-Lite system: citation faithfulness ≥99.5%, hallucination ≤1.0%, Tier A factual ≥99%, refusal correctness ≥98%, voice tier compliance, latency gates.

**Exit criteria:** All seven ship gates passing at threshold. Eval pipeline runs per-PR in <5 minutes.

### Phase 7 — Pre-launch dress rehearsal + legal publication (2 weeks)

Tracked by Cowork:

- Legal docs published with `support@tyndaleapp.net` + `privacy@tyndaleapp.net` filled in, analytics tool section updated to "Plausible" to match reality
- Plausible live; no advertising/retargeting trackers confirmed via DOM audit
- Free-tier abuse controls live (email + phone verification + Terms-based suspension power)
- End-to-end dress rehearsal with synthetic test users
- Pre-launch readiness checklist (developer spec §99) all items checked, including verification that the security-spine items (BAA chain green, attorney sign-off, etc.) are confirmed by Brock

Tracked outside Cowork (Brock + contacts):
- BAA chain confirmation (all nine critical-path BAAs at green)
- Attorney sign-off on Terms, Privacy Policy, Improvement Consent, State-Specific Rights Addendum

**Exit criteria:** Pre-launch checklist 100% green. Brock signs off on launch.

### V1-Lite launch

### Full V1 — begins immediately after V1-Lite ships (per Brock)

Full V1 expansion lights up immediately on V1-Lite launch. The expansion is additive per the docs: promote folded-in Lead Planner logic to standalone Legal Researcher (Task 19) and Strategist (Task 20) subagents, activate Code Validator (Task 21), add FHIR tools alongside the upload tools, build Document Generation Skill (Task 09) + Negotiation & Strategy standalone (Task 10) + Charity Care (Task 11), add the gated `send_email` path, and add the connect-insurance flow + letter review/approval UI in the app. Manual review of every appeal letter remains in place until Layer 3 (faithfulness check) ships or 90+ days of production data show zero "right form wrong substance" failures.

**Post-V1-Lite vision** (parked in backlog): QA agent + Compliance Scanner are the strongest first additions once Full V1 is stable.

---

## What I need from Brock to proceed

One thing:

1. **Explicit approval of this revised plan** as the V1-Lite working baseline. Adjustments welcome; an explicit "approved" or "approved with these changes" unblocks Phase 0.

Once that lands, Cowork produces **Phase 0 in detail** (integration contracts spec, monorepo layout, Plausible setup, dashboard scope confirmation) — still as a plan for sign-off, not Claude Code prompts to run. Code starts only when Brock signs off Phase 0.
