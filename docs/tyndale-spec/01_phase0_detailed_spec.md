# Phase 0 — Detailed Spec for Sign-Off

**Prepared by:** Cowork (PM/PdM)
**To:** Brock, via Phil (CTO)
**Date:** May 27, 2026
**Status:** For sign-off. Builds on the approved `00_v1lite_build_plan_for_brock_approval.md`. No code yet. After Brock signs off this Phase 0 spec, Phase 1 begins.

This document specifies everything Cowork owns in Phase 0:

1. Monorepo layout (`tyndale.git`)
2. Integration contracts the security/HIPAA spine builds against
3. Plausible setup
4. Dashboard scope confirmation
5. Parallel out-of-Cowork tracks (Brock's contacts) — for visibility, not Cowork-tracked
6. Exit criteria

Phase 0 is one week of work. No code commits to `main`. Outputs are: this document signed off, the monorepo skeleton designed (and committed as an initial scaffold in the empty `tyndale.git`), the integration contracts published for the security expert to build against, Plausible standing by, and the dashboard scope confirmed.

---

## 1. Monorepo layout

`tyndale.git` is a single monorepo. The layout below is the V1-Lite starting state. Full V1 adds directories under each top-level area, not new top-level areas.

```
tyndale/
├── intelligence-layer/         # Brock's authoring via Claude Code (Skills, subagents, tool descriptions, eval data)
│   ├── reference/              # principles, voice tiering, refusals, citations, glossary, discipline rules
│   ├── skills/                 # 8 Skills (V1-Lite uses Bill Error Detection, Cost Estimation, Coverage Connection)
│   ├── subagents/              # 6 subagent system prompts (V1-Lite uses Lead Planner + Bill Detective + Math Person)
│   ├── tools/descriptions/     # ~27 tool descriptions (V1-Lite uses the upload-extract + Qdrant subset)
│   ├── collections/            # schemas, ingestion templates, fixtures for the 4 Qdrant collections
│   ├── evals/                  # golden examples + synthetic generation scaffolding
│   └── operational/            # BAA tracker, handoff briefs, decision log
│
├── runtime/                    # Jonas's FastAPI monolith + tool implementations + hook wiring
│   ├── app/                    # FastAPI application code
│   │   ├── agents/             # Claude Agent SDK integration; Lead Planner orchestration
│   │   ├── tools/              # in-process Python implementations of the ~27 tools
│   │   ├── hooks/              # hook interface — security spine plugs in here
│   │   ├── routes/             # /v1/upload, /v1/audit, /v1/feedback, /health, etc.
│   │   ├── db/                 # Postgres models + migrations (case files, audit log, deadlines, findings)
│   │   ├── middleware/         # CORS, request logger (PHI-safe), error handler
│   │   ├── config/             # zod-style env validation, fail-fast on missing config
│   │   └── stubs/              # dev-mode stubs (fake Claude, fake OCR, fixture data)
│   ├── crons/                  # Proactive Monitor (nightly), Regulation Researcher (weekly)
│   ├── tests/                  # pytest + httpx
│   └── pyproject.toml
│
├── apps/
│   ├── mobile/                 # Phil's Expo project — RN universal (web + iOS + Android)
│   │   ├── app/                # Expo Router file-based routes
│   │   ├── components/         # shared UI components
│   │   ├── design-system/      # Tyndale palette (dark dashboard + cream marketing) + Inter font
│   │   ├── lib/                # api-client, auth, env access, feature flags
│   │   ├── assets/             # logo, icons, fonts
│   │   ├── app.config.ts       # Expo config
│   │   └── package.json
│   │
│   └── web-marketing/          # Next.js for SEO landing only — not the product
│       ├── app/                # App Router pages: /, /pricing, /privacy, /terms
│       ├── components/         # marketing components (hero, feature cards, footer)
│       └── package.json
│
├── packages/
│   └── shared/                 # TypeScript types shared between mobile, web-marketing, and runtime API contracts
│       ├── src/
│       │   ├── case-file.ts    # CaseFile, Finding, Coverage, EOB types
│       │   ├── feedback.ts     # FeedbackEvent (matches L05 capture schema)
│       │   ├── api-contract.ts # request/response types per route
│       │   └── auth.ts         # User, Session
│       └── package.json
│
├── infra/                      # Terraform for Azure deployment
│   ├── modules/                # reusable modules (container app, postgres, key vault, blob)
│   ├── envs/                   # per-environment configs (dev, staging, production)
│   │   ├── dev/
│   │   ├── staging/
│   │   └── production/
│   └── README.md
│
├── docs/                       # internal documentation (reference copies of spec docs)
│   ├── tyndale-spec/           # reference copy of the 47-file source folder + 7-file Additional Files folder
│   ├── decision-log.md         # Phase 0 onwards — every locked decision with date + owner
│   └── INDEX.md
│
├── .github/
│   └── workflows/              # CI: per-PR smoke evals (Braintrust), linting, type-checking, tests
│
├── .gitignore
├── .editorconfig
├── .nvmrc                      # node 20
├── package.json                # npm workspaces root
├── tsconfig.base.json
├── CLAUDE.md                   # context file for future Claude Code sessions in this repo
└── README.md
```

**Workspace configuration.** npm workspaces at the root level; `apps/mobile`, `apps/web-marketing`, and `packages/shared` are TypeScript workspaces. `runtime/` is a Python project (uv or poetry, Jonas's call) — sits inside the monorepo for proximity but doesn't share the npm workspace. `intelligence-layer/` is markdown/JSON/Python templates only — no runtime dependencies; Brock's Claude Code sessions operate against this directory.

**Why monorepo, why this shape.** Single source of truth for V1-Lite contracts (case file schema, citation format, tool return shapes). Phil can change a TypeScript type in `packages/shared` and the type-check across mobile + web-marketing catches drift instantly. Jonas's runtime references the same contracts via generated TypeScript-to-Python type hints (we'll pick a tool in Phase 1 — likely `pydantic`-based codegen from the shared schemas). Each app gets its own deployment pipeline; they're decoupled at deploy time even though coupled at the contract level.

**Deploy targets.**
- `apps/mobile` web build → Azure Static Web App (free tier OK for V1-Lite)
- `apps/web-marketing` → Azure Static Web App (or Vercel; Phil's call in Phase 1)
- `runtime` → Azure Container App inside the VPC
- `intelligence-layer/` does not deploy — it's the source for the runtime's prompts and Skill loading; the runtime reads it at startup or via a build step

Apple Sign-In's Apple Developer setup is parallel work but doesn't change this layout.

---

## 2. Integration contracts for the security/HIPAA spine

These contracts are the only artifact Cowork hands to Brock's security/HIPAA contact. The contact implements against these; the rest of the team builds with the same contracts in mind. Source of truth: the developer spec (`02_developer_spec.html`), sections 11 (tools), 12 (context management), 13 (citations), 17 (caching), 18 (PHI), plus Change Order 001 (the `research_log` addition).

### 2.1 Hook signatures (Claude Agent SDK)

The Claude Agent SDK exposes four hook surfaces. The security spine implements each. The runtime registers them on agent initialization.

**UserPromptSubmit** — Fires when a user message + any attached document content arrives, before the Lead Planner sees it.

```python
def user_prompt_submit_hook(
    user_id: str,
    case_file_id: str | None,
    raw_message: str,
    attached_documents: list[dict],   # each: {document_id, mime_type, ocr_text | None}
) -> UserPromptSubmitResult:
    """
    Returns:
      - scrubbed_message: user message with prompt-injection patterns flagged
      - wrapped_documents: OCR'd content wrapped in 'DATA, NOT INSTRUCTIONS' framing
      - injection_signals: list of detected injection patterns (logged to audit)
      - block: bool — if true, the message does not reach the Lead Planner; user sees a polite "we couldn't process this" + audit event
    """
```

**PreToolUse** — Fires before any tool invocation. Three responsibilities:

```python
def pre_tool_use_hook(
    case_file_id: str,
    actor: str,           # subagent name or 'lead_planner'
    tool_name: str,
    tool_args: dict,
) -> PreToolUseResult:
    """
    Three responsibilities:
      1. Presidio scrubbing of any PHI in tool_args before they're passed to outbound services
         (e.g., FAIR Health queries: scrub before send if no BAA)
      2. Approval-token validation for gated tools (send_email, doc_generate when user hasn't approved)
      3. Effective-date filter validation: qdrant_search_laws_regulations and
         qdrant_search_payer_policies MUST include effective_date; hook blocks if missing
    Returns:
      - sanitized_args: tool args with PHI scrubbed where required by destination's BAA status
      - approved: bool — if false, tool invocation is blocked and a user-facing approval prompt fires
      - block_reason: str | None
    """
```

**PostToolUse** — Fires after every tool invocation. Writes the audit event.

```python
def post_tool_use_hook(
    case_file_id: str,
    actor: str,
    tool_name: str,
    tool_args_scrubbed: dict,    # already scrubbed by PreToolUse
    tool_result: dict,
    duration_ms: int,
    outcome: Literal["success", "error", "timeout", "blocked"],
    error_details: str | None,
) -> None:
    """
    Writes an audit_events row (encrypted payload). No return; failures here trigger ops alert.
    Also measures cache hit rate and cost accounting in the same write.
    """
```

**Stop** — Fires when the agent produces final user-facing output. Runs citation Layer 2 resolution.

```python
def stop_hook(
    case_file_id: str,
    actor: str,
    generated_output: str,
    retrieved_chunks: list[dict],  # chunks retrieved this session with source_ids
    attempt: int,                  # which generation attempt (1, 2, 3)
) -> StopResult:
    """
    Parses generated_output for citation markers ([authority §section, src_id]).
    For each marker, verifies the src_id resolves to a chunk in retrieved_chunks.
    Returns:
      - resolved: bool — true iff every citation resolves
      - unresolved_citations: list[str] — for diagnostics
      - action: 'ship' | 'regenerate' | 'human_review'
        * ship if resolved
        * regenerate if unresolved and attempt < 3
        * human_review if unresolved and attempt == 3
    """
```

**Crisis classifier** — A separate Haiku 4.5 classifier screens chat input for crisis language *before* normal processing. Per Brock's reaffirmation (clean decline, no routing), a positive signal triggers the Category 2 refusal template immediately, bypassing the Lead Planner. Implementation is the security spine's call (lives logically near the UserPromptSubmit hook); contract: takes the raw user message, returns `crisis_detected: bool`.

### 2.2 Audit log payload schema (Postgres `audit_events`)

Source: developer spec §18. Encryption is AES-GCM field-level on `payload_encrypted` with keys in Azure Key Vault, rotated every 90 days.

```sql
CREATE TABLE audit_events (
  event_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp         TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_type        TEXT NOT NULL CHECK (event_type IN (
                      'tool_invocation', 'subagent_call', 'model_call',
                      'user_action', 'system_action', 'hook_invocation'
                    )),
  actor             TEXT NOT NULL,              -- subagent name | user_id | system_process
  case_file_id      UUID,
  user_id           UUID,
  payload_encrypted BYTEA NOT NULL,             -- AES-GCM ciphertext of the full payload
  payload_hash      BYTEA NOT NULL,             -- SHA-256 of the unencrypted payload, for tamper detection
  key_version       INT NOT NULL,               -- which Key Vault key version encrypted this row
  model_version     TEXT,                       -- pinned model ID if model call
  skill_version     TEXT,                       -- pinned Skill commit SHA if Skill involved
  prompt_template_version TEXT,
  retrieved_chunks  JSONB,                      -- array of chunk IDs for citation reconstruction
  tools_invoked     JSONB,                      -- array of tool names
  outcome           TEXT NOT NULL CHECK (outcome IN ('success', 'error', 'timeout', 'blocked')),
  error_details     TEXT                        -- scrubbed; null on success
);

CREATE INDEX idx_audit_events_case_file ON audit_events(case_file_id);
CREATE INDEX idx_audit_events_user      ON audit_events(user_id);
CREATE INDEX idx_audit_events_timestamp ON audit_events(timestamp);
```

**Retention:** 7 years. Archived to Azure Blob after that.

**Access:** No standing access. Per-investigation request workflow. Every access logged in a meta-audit table (same schema, recursive). Brock reviews access requests monthly.

### 2.3 Case file schema (Postgres + `research_log`)

Source: developer spec §12 (artifact pattern + plan-to-memory) + Change Order 001 item 4 (research_log).

```sql
CREATE TABLE case_files (
  case_file_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL REFERENCES users(user_id),
  status                TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved', 'archived')),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Documents the user has uploaded for this case (bills, EOBs, insurance card, plan summary)
  documents             JSONB NOT NULL DEFAULT '[]',
  -- Structured coverage data — matches the FHIR Coverage return shape (so subagents are source-agnostic)
  coverage              JSONB,
  -- Structured EOB data — same shape as fhir_get_eobs return
  eobs                  JSONB NOT NULL DEFAULT '[]',
  -- Lead Planner's plan-to-memory (current plan + version history)
  plan_current          JSONB,
  plan_history          JSONB NOT NULL DEFAULT '[]',
  -- research_log per Change Order 001 item 4
  research_log          JSONB NOT NULL DEFAULT '[]',
    -- Each entry: {
    --   timestamp: ISO8601,
    --   topic: str,            -- the question being investigated
    --   what_was_checked: str, -- which collection/source/tool
    --   result_summary: str,
    --   finding_id: UUID | null  -- if a Finding was produced
    -- }
  -- Optimistic locking
  version               INT NOT NULL DEFAULT 1
);

CREATE TABLE findings (
  finding_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_file_id          UUID NOT NULL REFERENCES case_files(case_file_id),
  finding_type          TEXT NOT NULL,         -- 'payer_side', 'provider_side', 'encounter_mismatch'
  category              TEXT NOT NULL,         -- e.g., 'bundling', 'cost_sharing_miscalculation'
  subagent_source       TEXT NOT NULL,
  voice_tier            TEXT NOT NULL CHECK (voice_tier IN ('A', 'B', 'C')),
  facts                 JSONB NOT NULL,        -- Tier A structured facts
  legal_claim           JSONB,                 -- Tier B claim with citation
  recommendation        JSONB,                 -- Tier C action + reasoning
  status                TEXT NOT NULL DEFAULT 'open',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE deadlines (
  deadline_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_file_id          UUID NOT NULL REFERENCES case_files(case_file_id),
  deadline_date         DATE NOT NULL,
  deadline_type         TEXT NOT NULL,         -- e.g., 'erisa_internal_appeal', 'aca_external_review'
  description           TEXT NOT NULL,
  status                TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'missed')) DEFAULT 'pending',
  notified_thresholds   JSONB NOT NULL DEFAULT '[]'  -- which thresholds have been notified (14d/7d/3d/24h)
);

CREATE INDEX idx_findings_case_file       ON findings(case_file_id);
CREATE INDEX idx_deadlines_case_file_date ON deadlines(case_file_id, deadline_date);
```

**Lead Planner usage (per Change Order 001):**
- Writes a `research_log` entry on every non-trivial investigation step before re-investigating
- Reads `research_log` before starting any subagent invocation — implements the "what do I now know?" step of the proactive thinking loop
- On app open, loads case files where `status IN ('open', 'in_progress')` plus the most recent few `findings` and `deadlines` for the status-forward greeting

### 2.4 Feedback → de-identification handoff

Source: V1-Lite tasks L05 (capture schema) and L06 (de-identify + promote pipeline) + Change Order 001 (encounter-verification confirmations as feedback events).

```
Feedback flow:
  1. User UI emits a feedback event matching feedback/capture_schema.json (from L05)
  2. Runtime persists the event in Postgres (`feedback_events` table)
  3. Runtime writes the event to a Postgres-backed queue (`feedback_triage_queue`)
  4. Security spine's de-identification runner (Python script, lives in runtime/crons/ or runtime/workers/) reads the queue:
     - Filters to events where improvement_consent = true
     - Runs Presidio + custom recognizers over: OCR'd document text, extracted values, free-text feedback
     - Writes de-identified candidates to `feedback_deid_candidates` table; failures stay in audit log only
  5. Brock's weekly triage session reads `feedback_deid_candidates`, promotes selected events to golden examples (evals/golden/)

Contracts the security spine implements:
  - Input: read from feedback_triage_queue (event payload matches L05 capture_schema.json)
  - Output: write to feedback_deid_candidates (typed-placeholder text in payload, plus pass/fail metadata)
  - SLA: events with consent=true are processed within 24 hours
  - Failure mode: if de-id confidence is below 0.95 on any field, mark fail; event stays in audit log only
```

The `feedback_events` and `feedback_deid_candidates` Postgres tables are defined in Phase 1 by Jonas; the de-id runner script is the security spine's deliverable.

---

## 3. Plausible setup

- **Account:** Create a Plausible Business account at plausible.io for `tyndaleapp.net`.
- **Cost:** ~$9/month at our V1-Lite traffic projection (under 10K monthly pageviews). Scales with traffic.
- **Domain configuration:** Add `tyndaleapp.net` and `app.tyndaleapp.net` (if we end up using a subdomain for the app vs marketing).
- **Goals to configure (custom events):** `signup_completed`, `bill_uploaded`, `audit_completed`, `recommendation_accepted`, `subscription_started`, `subscription_canceled`.
- **Script install:**
  - `apps/web-marketing` — Plausible's standard script tag in `app/layout.tsx`
  - `apps/mobile` (Expo Router web build only) — Plausible's standard script tag; mobile-native traffic is not tracked in V1-Lite (PostHog later if needed)
- **Privacy Policy:** Section 8 already references "privacy-respecting first-party analytics." Once Plausible is live, update the exact name to "Plausible Analytics" before legal publication (Phase 7).
- **DOM audit:** Confirm no advertising/retargeting trackers on any page handling health or billing data. Run a pre-launch audit in Phase 7.
- **Data residency:** Use Plausible's EU-hosted option for stronger privacy posture, but US-hosted is acceptable; CTO's call.

No GDPR cookie banner needed because Plausible doesn't set cookies. State-specific consent-banner work in Phase 7 will only kick in if we add anything beyond Plausible.

---

## 4. Dashboard scope confirmation

The V1-Lite L08 spec describes an upload-centric scaffold. Brock's screenshots show a substantially broader logged-in dashboard. Cowork is treating the screenshots as the design target. Recording here for traceability; if Brock disagrees, flag now.

**Logged-out marketing landing (`apps/web-marketing`):**
- Dark teal hero with "Tyndale. Welcome to the App." headline
- Google Sign-In CTA (Apple Sign-In deferred to fast-follow per locked decision)
- Six feature cards in cream-light section: Easy Sign-In, Simple to Use, Insurance Card Scanner, Your Data Stays Safe, AI Health Assistant, Always Up to Date
- Dark teal "Built for you" footer section with Fast / Secure / Reliable badges
- Permanent footer disclaimer: "Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice."

**Logged-in dashboard (`apps/mobile`):**
- Dark navy background with the Tyndale logo top-left
- "Welcome back, {first_name}." hero card
- Coverage status tiles row 1:
  - Deductible (amount met / total, sage progress bar, amount remaining)
  - Out-of-Pocket Max (amount met / total, amber progress bar, amount remaining)
- Coverage status tiles row 2:
  - Copay — PCP Visit
  - Copay — ER Visit
  - Copay — Specialist
  - Amount Saved This Year (sage-tinted, success styling)
- "QUICK ACTIONS" section header, then four cards:
  - Check a Bill (Bill Error Detection + Math Person)
  - Plan a Visit (Plan a Visit Skill)
  - Find a Doctor (Find a Doctor Skill)
  - Estimate Costs (Cost Estimation Skill)
- Bottom-anchored teal CTA: "Chat with AI Assistant — Available now" → opens chat-anchored interaction with the Lead Planner

**Per Change Order 001 item 3 (lead-with-status):** When a returning user with open cases opens the app, the hero card area shows "Here's where your X open issues stand," driven by live case-file state, *before* the static welcome message. Empty state (no open cases) shows the standard "What would you like to do today?" prompt.

**Skills not in V1-Lite quick actions:** Charity Care, Negotiation & Strategy (folded into Lead Planner), and Document Generation (deferred to Full V1). The four quick actions match the four Skills V1-Lite ships.

If Brock disagrees with anything above, flag before Phase 1 starts so Phil doesn't build the wrong thing.

---

## 5. Parallel out-of-Cowork tracks

Listed for visibility. Cowork doesn't track or own these; Brock and his contacts do. Their status affects when Phases 5–7 can complete, so they need to be making progress in parallel.

| Track | Owner | Phase dependency | Notes |
|---|---|---|---|
| Legal counsel engagement + legal-pack review | Brock | Phase 7 (legal publication) | Long-lead. |
| AMA CPT license procurement | Brock | Phase 5 (`billing_codes` ingestion) | Phases 1–4 don't depend on it. |
| FAIR Health license procurement | Brock | Phase 5 (Cost Estimation accuracy) | Medicare-RVU fallback works without it. |
| Anthropic HIPAA-ready BAA | Brock + security contact | Phase 4 (PHI spine integration) | Defense-in-depth posture given non-HIPAA-covered status. |
| Azure BAA | Brock + security contact | Phase 4 | Covers Container Apps, Postgres, Blob, Key Vault, Monitor, Document Intelligence. |
| AWS BAA (Bedrock) | Brock + security contact | Phase 4 | Second Claude fallback path. |
| SendGrid Email API Pro (HIPAA-eligible tier + BAA) | Brock + security contact | Phase 1 (account/notification email) | Standard tier does not include BAA. |
| Voyage AI BAA | Brock + security contact | Phase 5 (embeddings on user content if applicable) | Scrub-before-send fallback. |
| Stripe BAA | Brock | Phase 4 (Stripe integration) | Defense-in-depth; PHI shouldn't flow to Stripe by design. |
| Observability vendor BAA | Brock + security contact | Phase 1 (app monitoring) | Vendor TBD; Datadog and Honeycomb both offer BAAs. |
| Azure tenancy provisioning | Brock + security contact | Phase 1 (FastAPI deploy + Qdrant) | Standing this up Day 1 of Phase 1. |
| Apple Developer enrollment + Services ID | Brock | Native iOS App Store submission (post-V1-Lite-web-launch) | Parallel work during Phases 2–4. |
| Security/HIPAA infrastructure build | Brock's contact | Integrates throughout Phases 2–4 | Implements against Section 2 contracts above. |

If any of the items in this table aren't progressing in parallel during the indicated phase, Cowork flags it as a launch risk to Brock — but Cowork doesn't drive the work.

---

## 6. Phase 0 exit criteria

Phase 0 is complete when:

- [ ] This document is signed off by Brock
- [ ] `tyndale.git` has an initial commit with the monorepo skeleton (empty directories per Section 1, root configs, CLAUDE.md, README placeholder)
- [ ] `docs/decision-log.md` exists with every locked decision recorded
- [ ] `docs/tyndale-spec/` has a copy of the 47 + 7 = 54 source documents from Brock's two folders
- [ ] Integration contracts (Section 2) are committed to `docs/integration-contracts.md` and shared with Brock's security/HIPAA contact
- [ ] Plausible account exists with `tyndaleapp.net` configured (does not need to be receiving traffic yet)
- [ ] Dashboard scope (Section 4) is either confirmed by Brock or modified with his pushback
- [ ] Out-of-Cowork tracks (Section 5) are confirmed to be progressing in parallel (status check, not Cowork-managed)

When all eight items are checked, Phase 1 begins.

---

## What I need from Brock to proceed

One thing:

- **Sign-off on this Phase 0 spec.** Adjustments welcome. After sign-off, Phase 1 begins on the schedule in the parent plan.

If Brock or Phil wants any of the directory structure, integration contracts, or dashboard scope changed before sign-off, this is the moment.
