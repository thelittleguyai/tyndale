# Task L09 — V1-Lite handoff brief & upgrade map

**Phase:** L3 · V1-Lite wrap-up
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** L01–L07, plus full Build Kit Task 32 (full handoff brief)

## What this task does

The capstone V1-Lite document. Tells Phil, Jonas, and Josh exactly what to build for V1-Lite, what's deferred, and — critically — the upgrade map showing how to expand V1-Lite into full Tyndale without rework.

## Prompt to paste into Claude Code

```
Create `operational/v1lite_handoff_brief.md` — the V1-Lite engineering
handoff. This is the V1-Lite counterpart to the full handoff brief.

First read:
- operational/handoff_brief.md (the FULL handoff — your reference)
- v1_lite/01_v1lite_scope_and_compatibility.html (the scope spec)
- MODES.md

Structure:

# V1-Lite Engineering Handoff Brief

## TL;DR

V1-Lite ships first: document upload (not FHIR), 3 agents (Lead Planner
+ Bill Detective + Math Person), no letter generation, plus a feedback
loop from day one. It shares all contracts with full Tyndale, so the
upgrade is expansion, not rewrite. Read operational/handoff_brief.md for
the full-version context; this document is the V1-Lite delta.

## What ships in V1-Lite

### Intelligence layer (3 agents)
- Lead Planner — COLLAPSED variant at
  subagents/lead_planner/v1_lite/system_prompt.md. Folds in legal
  research + strategy guidance. Does NOT draft letters.
- Bill Detective — identical to full (subagents/bill_detective/)
- Math Person — identical to full (subagents/math_person/)

### Data acquisition: document upload (not FHIR)
- Implement the upload_extract_* tools (tools/descriptions/v1_lite/)
  using Azure Document Intelligence for OCR/extraction
- These produce the SAME case file fields as the FHIR tools — subagents
  are agnostic to source
- Confidence scoring on extraction; low-confidence triggers user
  confirmation (the Lead Planner handles the ask per P1)

### Skills (subset)
- Bill Error Detection — identical, the core value
- Cost Estimation — identical
- Coverage Connection — manual-upload mode (skills/coverage_connection_fhir/,
  the V1-Lite reference files added in Task L03)
- Find a Doctor, Plan a Visit — OPTIONAL, include if time allows
- Negotiation & Strategy — used for DIAGNOSTIC logic only (the Lead
  Planner reads the diagnostic index to pick a framework), NOT for letter
  output
- DEFERRED Skills (don't build for V1-Lite): Document Generation,
  Negotiation & Strategy as a full standalone, Charity Care Eligibility

### Knowledge collections (all 4)
- billing_codes, error_detection_rules, laws_regulations, payer_policies
- Identical to full. Josh runs ingestion. All the §6–§9 discipline applies.

### The PHI spine (required day one — NOT deferrable)
- Dual-stream logging, Presidio scrubbing, encrypted audit log
- Citation enforcement Layers 1 + 2
- LiteLLM Claude-only routing
- BAA chain (minus FHIR-related: no 1upHealth BAA needed yet)

### Feedback & learning loop (new, day one)
- Capture (feedback/capture_schema.json) wired into the web app
- Two-consent model (feedback/consent_model.md) — improvement consent
  is opt-in, separate from service consent
- De-identify → triage → promote pipeline (feedback/pipeline_spec.md)
- The de-identification reuses the SAME Presidio pipeline as the PHI spine

### Web app (mobile-friendly)
- Phil hardens the web_app_scaffold/ into production
- Upload-centric, responsive, chat-anchored results, feedback capture,
  improvement-consent toggle, case tracker with deadlines

### Payments
- Stripe, $11.99/mo & $100/yr unlimited (same as full V1)

## What's deferred to the full upgrade

- FHIR OAuth + 1upHealth integration
- Legal Researcher, Strategist, Code Validator as standalone subagents
- Document Generation, Negotiation & Strategy (standalone), Charity Care
  Skills
- The gated send_email path (no outbound letters in V1-Lite)
- Full eval case volume (V1-Lite starts with fewer golden + synthetic
  cases; the feedback loop grows them)

## BAA chain for V1-Lite

From the full BAA tracker (operational/baa_tracker.md), V1-Lite needs:
- Anthropic, Azure, AWS — yes (same as full)
- Postmark — only if you send ANY email; if V1-Lite sends no outbound
  letters, you may defer until you add transactional email (still need
  it for account/notification emails — confirm scope)
- Voyage AI — yes (embeddings; same fallback rules)
- FAIR Health — yes if cost estimation is in V1-Lite (same fallback)
- Stripe, observability — yes (defense-in-depth)
- 1upHealth — NOT needed for V1-Lite (no FHIR). Add at upgrade.
- Braintrust — synthetic only, no BAA needed (same as full)

## The upgrade map: V1-Lite → full Tyndale

| Component | Upgrade action | Rework risk |
|-----------|---------------|-------------|
| Coverage data | Add FHIR tools alongside upload tools; add "connect insurance" branch to Lead Planner. Upload path stays. | None — pure addition |
| Lead Planner | Replace v1_lite/system_prompt.md with the full pure-coordinator system_prompt.md. The folded-in logic moves to subagents. | None — both prompts already exist |
| Legal Researcher | Activate the standalone subagent (prompt already written, Task 19). Lead Planner stops doing inline legal research. | None — prompt exists |
| Strategist | Activate the standalone subagent (Task 20). Wire in Document Generation. | Low — prompt exists, wiring is new |
| Code Validator | Activate the standalone subagent (Task 21). Bill Detective offloads code lookups. | None — prompt exists |
| Letter generation | Build Document Generation (Task 09), Negotiation & Strategy standalone (Task 10), Charity Care (Task 11) Skills. Add gated send_email. NOW informed by real V1-Lite outcome data. | New build — but data-informed and lower-risk because of the feedback corpus |
| Web app | Add connect-insurance flow + letter review/approval screens. Upload UI stays. | Low — additive screens |
| Evals | Volume grows naturally via the feedback loop. | None |
| Feedback loop | No change — already built and running, with accumulated data. | None |

## Suggested V1-Lite build sequence (engineering)

Week 1: Azure tenancy, Postgres + audit log, LiteLLM skeleton, BAA kickoff
Week 2: PHI spine (dual-stream logging, Presidio), Qdrant deployment
Week 3: Upload + OCR pipeline (Azure Document Intelligence), upload_extract_* tools
Week 4: Claude Agent SDK, collapsed Lead Planner + Bill Detective + Math Person
Week 5: Knowledge collection ingestion (Josh), tool implementations
Week 6: Feedback loop (capture, consent, de-identify, triage, promote)
Week 7: Web app hardening (Phil), Stripe, citation Layer 2
Week 8: Eval wiring, synthetic generation, dress rehearsal
Week 9: Ship gates, V1-Lite launch

This is faster than the full timeline because: no FHIR, 3 agents not 6,
no letter generation, fewer Skills. The PHI spine and the feedback loop
are the parts you don't get to shortcut.

## Decisions NOT to relitigate

Same locked decisions as full Tyndale (see operational/handoff_brief.md).
PLUS the V1-Lite-specific calls:
- 3-agent collapse (fold legal + strategy into Lead Planner) — locked
- All 4 collections in V1-Lite — locked
- Defer letter generation — locked
- Feedback loop from day one, with two-consent model + mandatory
  de-identification — locked
- Upload path stays even after FHIR goes live — locked
- THE INDEPENDENT AUDIT DOCTRINE — locked and foundational. The EOB is
  audited, never trusted. Math Person computes member responsibility
  independently, then compares against both the bill and the EOB (three
  numbers). Payer-side errors get equal weight to provider-side. Encounter
  verification (user confirms the service happened, in plain language)
  runs before charges are trusted. See reference/principles.md.
- SINGLE BRAND, BETA FRAMING — locked. V1-Lite ships under the Tyndale
  name, explicitly labeled early-access/beta. It is NOT a separate
  throwaway brand. Reason: V1-Lite is the same product as full Tyndale
  with one input method swapped (manual upload while 1upHealth integration
  is built) — not a different or riskier product. A disposable brand would
  forfeit the compounding trust, user continuity, and the upgrade story
  ("remember calling the insurer yourself? now Tyndale does it for you"),
  and would create a compliance/trust problem around who users consented
  to share PHI with. The beta label does the expectation-setting work a
  second brand was meant to do, at none of the cost.

## Final word

V1-Lite exists to get real value into users' hands faster AND to start
the data flywheel. Every bill a user uploads, every piece of feedback,
every outcome, every encounter confirmation — with consent and
de-identification — makes the full version better. By the time you build
letter generation, you'll have real cases with known outcomes to build
and evaluate against. The sequencing is the strategy: ship the
lower-risk surface, gather the data, then build the high-value feature
well. And remember the doctrine above all: Tyndale audits, it does not
trust. That's what makes it worth paying for.

Commit with message "Add V1-Lite handoff brief and upgrade map".
```

## Done when

- `operational/v1lite_handoff_brief.md` exists with the full content
- The upgrade map table is complete
- The build sequence is included
- Git log shows the commit

## This completes the V1-Lite Build Kit

After L08, you have everything needed to build and ship V1-Lite, then expand into full Tyndale using the original Build Kit's deferred tasks. The two kits compose: V1-Lite reuses ~18 of the original 32 tasks, adds these 8, and defers ~9 to the upgrade.
