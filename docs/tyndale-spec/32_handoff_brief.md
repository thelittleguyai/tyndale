# Task 32 — Write the engineering handoff brief

**Phase:** 7 · Documentation
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** All previous phases — this is the final task

## What this task does

The capstone document. Explains to Phil, Jonas, and Josh what's been built in this repo, what they need to build in the runtime repo, and how the two fit together. This is the document they read on Day 1 of the engineering build.

## Prompt to paste into Claude Code

```
Create `operational/handoff_brief.md` — the engineering handoff
document. This is what Phil, Jonas, and Josh read first.

Structure:

# Engineering Handoff Brief

Welcome. You're picking up Tyndale's intelligence layer at the point
where the non-runtime work is complete. This document tells you what's
been done, what's left, and how the pieces fit together.

## TL;DR

- Brock built the prompts, Skills, tool descriptions, knowledge
  collection scaffolding, and eval test data — all in THIS repo.
- You're building the runtime: FastAPI monolith, LiteLLM proxy, Qdrant
  deployment, Postgres schemas, FHIR OAuth, hooks, Stripe — in the
  separate engineering repo.
- The two repos are loosely coupled via well-defined contracts (tool
  signatures, Skill structure, case file schema).
- Pre-launch ship gates are documented in section 21 of the developer
  build spec. All 7 must pass before V1 launches.

## What's built in THIS repo

### Reference foundation (`reference/`)
6 cross-cutting reference files that every Skill, subagent, and tool
description references. Read these first:

- `principles.md` — six operating principles (P1–P6). These are the
  operational interpretation of Tyndale's "thinks 5 steps ahead" promise.
- `voice_tiering.md` — three-tier voice framework (Tier A factual,
  Tier B legal, Tier C strategic). Every output complies with these tiers.
- `refusals.md` — five out-of-scope categories with clean-decline
  templates. No routing to external resources.
- `citations.md` — standard citation format. Layer 2 resolver depends
  on this format for programmatic verification.
- `glossary.md` — standard terms for codes, payers, statutes used
  across all prompts.
- `discipline_rules.md` — every discipline rule from the 22
  architectural decisions, consolidated.

### Skills (`skills/`)
8 Skills authored, each as a directory with SKILL.md + reference files.
Three Skills have diagnostic indexes (`00_diagnostic_index.md`) loaded
first before deeper reference files:

- Bill Error Detection — with diagnostic index + 18 reference files
- Document Generation — 21 letter types with templates
- Negotiation & Strategy — with diagnostic index + 11 framework files
- Charity Care Eligibility — with diagnostic index + 10 reference files
- Cost Estimation, Coverage Connection & FHIR, Find a Doctor, Plan a Visit

Skills are markdown files. Your job in the runtime is to load them into
the Lead Planner / subagent context per the Claude Agent SDK's Skill
loading pattern.

### Subagent system prompts (`subagents/`)
6 versioned system prompts:
- Lead Planner (Sonnet 4.6) — coordinator
- Bill Detective (Sonnet 4.6) — bill analysis
- Math Person (Sonnet 4.6) — coverage math
- Legal Researcher (Sonnet 4.6) — legal RAG
- Strategist (Opus 4.7) — strategic decisions
- Code Validator (Haiku 4.5) — code validity lookups

Each subagent has a CHANGELOG.md tracking semver versions.

### Tool descriptions (`tools/descriptions/`)
27 tool description files. Each describes: what it does, when to use,
when NOT to use, args, returns, errors, which subagents use it.

YOUR job: implement these tools as Python functions in the runtime.
Use the descriptions verbatim as the tool's docstring / Claude Agent
SDK tool description. The descriptions were intentionally drafted to
maximize task completion (40% improvement per Anthropic's research).

### Knowledge collections (`collections/`)
- `schemas/` — JSON Schema for each of the 4 collections
- `ingestion/` — Python script templates with TODO markers
- `fixtures/` — ~20 records per collection for local dev testing

YOUR job: implement the TODO sections in ingestion scripts
(extract_records_from_source, common.py clients, validate_metadata).
Run ingestion for production data — billing_codes, error_detection_rules,
laws_regulations, payer_policies.

### Eval test data (`evals/`)
- `golden/` — directory structure + schema for ~400–600 expert-labeled
  examples. Brock is authoring these on an ongoing cadence.
- `synthetic/` — 12 Opus 4.7 generation prompts + runner script for
  ~2,000 adversarial cases.

YOUR job: wire Braintrust + Arize Phoenix per section 20 of the
developer spec. Run the synthetic generation. Stand up per-PR smoke
evals + nightly full evals.

### Operational (`operational/`)
- `baa_tracker.md` — Brock owns BAA execution; status updates in this file
- `handoff_brief.md` — this document

## What's NOT built (your work)

### Application runtime
- FastAPI monolith hosting Lead Planner + subagents + hooks + tools
- Claude Agent SDK integration (subagent spawning, allowed_tools per
  subagent, hook lifecycle)
- Effort scaling logic in Lead Planner (hard rules + judgment on
  ambiguous cases)
- Plan-to-memory pattern (Lead Planner writes plan to case file before
  complex work)
- Artifact pattern (subagents write findings to Postgres; Lead Planner
  reads pointers, not full payloads)

### Infrastructure
- Azure tenancy: Container Apps, Postgres Flexible Server, Blob, Key Vault,
  Monitor, Document Intelligence, Foundry
- VPC with no public ingress for Qdrant, LiteLLM proxy
- Networking, security groups, secrets management

### LiteLLM proxy
- Self-hosted deployment inside Azure VPC
- Claude-only fallback chain (Anthropic direct → Bedrock → Foundry → maintenance-mode)
- Prompt structure enforcement (cache tier boundaries)
- Weekly short-lived key rotation
- Per-route allow-lists
- Request-level audit logging

### Qdrant
- Self-hosted deployment on Azure Container Apps
- Daily snapshots to Azure Blob with 30-day retention
- Restore drills twice yearly
- Performance targets enforced (p95 <50ms, recall@10 ≥0.95)

### Hooks
- UserPromptSubmit — prompt injection scanning, OCR content wrapping
- PreToolUse — Presidio scrubbing, approval-token validation,
  effective-date filter validation
- PostToolUse — audit log writes, cache hit-rate measurement, cost
  accounting
- Stop — citation Layer 2 resolution, regeneration on failure

### PHI handling
- Dual-stream logging (Azure Monitor for scrubbed; Postgres audit_events
  for encrypted full fidelity)
- AES-GCM field-level encryption on audit log
- Azure Key Vault integration with 90-day key rotation
- Presidio + custom recognizers (insurance member IDs, MRNs, payer
  claim IDs, etc.)

### FHIR
- SMART-on-FHIR OAuth flow
- 1upHealth integration
- Token storage and refresh
- Coverage / ExplanationOfBenefit / Claim parsing

### Postgres
- Schema migrations for case files, findings, deadlines, audit log
- NCCI and MUE structured tables (loaded separately from Qdrant)
- Optimistic locking for concurrent updates

### Stripe
- $11.99/mo and $100/yr subscription tiers
- Family $29.99 within 90 days post-launch
- Chronic Care tier at Stage 3
- Webhook handling

### Crons
- Proactive Monitor (nightly 02:00 UTC)
- Regulation Researcher (weekly Sundays 03:00 UTC)

### Pre-launch benchmarks
Two benchmarks that Josh owns:
- voyage-context-3 vs voyage-3-large on laws_regulations
  (NDCG@10 ≥3 point delta required to ship with voyage-context-3)
- Presidio scrubbing accuracy on hand-labeled medical bills/EOBs
  (≥98% direct-identifier recall required to ship)

### Eval platform
- Braintrust integration with GitHub Actions (per-PR smoke evals)
- Arize Phoenix self-hosted for production trace export
- LLM judge configuration (Opus 4.7)
- Calibration against golden set (Cohen's κ ≥ 0.6)
- Ship gate enforcement (7 thresholds)

## How to start

### Week 1 — Read and align

1. Read the developer build spec (HTML, delivered separately) end-to-end
2. Read this handoff brief
3. Read `reference/discipline_rules.md` (the consolidated rules)
4. Read the 6 subagent system prompts to understand the agent shape
5. Skim the Skills to understand the playbook architecture
6. Schedule a 90-min walkthrough with Brock

### Week 2 — Infrastructure foundations

1. Stand up Azure tenancy
2. BAA execution kickoff (Brock owns this; engineering provides input
   on scope per vendor)
3. Initial Postgres schema + audit log table
4. LiteLLM proxy deployment skeleton

### Week 3-4 — Agent SDK integration

1. Claude Agent SDK setup
2. Lead Planner skeleton + 1 subagent (Code Validator — simplest)
3. Tool implementations: pg_case_file_get, pg_upsert_finding, qdrant_search_billing_codes
4. Hook implementations: PreToolUse (PHI scrubbing skeleton)

### Week 5-8 — Subagents and Skills

1. Remaining subagents
2. Skill loading mechanism
3. Tool implementations: remaining ~22 tools
4. Hook implementations: Stop hook (citation resolver), UserPromptSubmit

### Week 9-12 — Knowledge layer + FHIR

1. Qdrant deployment hardening
2. Run ingestion (Josh primarily)
3. FHIR OAuth + 1upHealth integration (Jonas primarily)
4. Stripe integration (Jonas primarily)
5. Crons (both)

### Week 13-14 — Evaluation infrastructure

1. Braintrust integration
2. Arize Phoenix deployment
3. Synthetic case generation (Brock runs Task 29's script)
4. Eval suite assembly

### Week 15-16 — Pre-launch benchmarks + dress rehearsal

1. Voyage embedding benchmark (Josh)
2. Presidio scrubbing benchmark (Josh)
3. End-to-end dress rehearsal with synthetic test users
4. All 7 ship gates met → V1 launch

This timeline is aggressive. Adjust based on actual hours available and
unforeseen issues. The dependencies are accurate; the sequencing is
flexible.

## Decisions you should NOT relitigate

The 22 architectural decisions are locked. They reflect substantial
research and tradeoff analysis. If you encounter a decision that seems
wrong, raise it with Brock — don't quietly change course.

Specific things NOT to change without Brock's sign-off:
- Model assignments (Lead Planner = Sonnet 4.6; Strategist = Opus 4.7; etc.)
- The 8 Skills inventory and the diagnostic index pattern
- The 4 Qdrant collections and what goes in each
- The two-tier prompt caching strategy
- The Claude-only fallback for user-facing reasoning
- The clean-decline-with-no-routing refusal pattern (especially mental
  health crisis — this was the most-debated decision; current call stands)
- The artifact pattern (case file as central state, minimal payloads
  between agents)
- The seven ship gates and their thresholds

## Decisions you CAN make on your own

- Implementation details that don't affect external contracts
- Coding style, organization within the runtime repo
- Choice of testing libraries, code quality tools
- Operational tooling (monitoring dashboards, alerting setup)
- Database migration tooling
- CI/CD pipeline shape
- Production deployment topology details (autoscaling, replication)

## Contact and questions

- Architecture questions: Brock
- Anthropic/Claude API questions: Anthropic support, also Brock
- Azure/AWS infrastructure questions: cloud vendor support, also you
- BAA status: Brock
- Skill or subagent prompt changes: PRs into this repo, Brock reviews
- Tool description changes: PRs into this repo, two-person review

## Final word

The intelligence layer you're building is the heart of Tyndale's product
promise. The discipline rules aren't bureaucracy — they're how Tyndale
avoids the failure modes (hallucinated citations, PHI leaks, outcome
predictions) that have damaged other AI-in-healthcare products.

If something feels off, raise it. If a rule seems wrong, raise it. If
the build pace is unsustainable, raise it. Better to slow down and
ship right than to ship a system that breaks the product promise.

Welcome aboard.

Commit with message "Add engineering handoff brief (Phase 7 complete)".
```

## Done when

`operational/handoff_brief.md` exists with the full content. Git log shows the commit.

## What's next

This is the final task in the Brock-buildable build kit. After Task 32, the work transitions to engineering. The 7 ship gates in the developer build spec govern when V1 actually launches.
