# Integration Contracts — Security/HIPAA Spine

**This file is the contract surface that Brock's security/HIPAA contact builds against, and
it is the source of truth for those contracts.** It defines the four Claude Agent SDK hook
signatures, the encrypted audit-log payload schema, the case-file schema (including the
`research_log` field), and the feedback → de-identification handoff. The security/HIPAA
contact implements against the interfaces below; the rest of the team builds with the same
contracts in mind. If any interface here needs to change, change it **here first** and notify
the contact — nothing downstream should diverge from this file.

> Extracted verbatim from Section 2 of the Phase 0 detailed spec
> ([`docs/tyndale-spec/01_phase0_detailed_spec.md`](tyndale-spec/01_phase0_detailed_spec.md)).
> Underlying source of truth for the spec itself: the developer spec (`02_developer_spec.html`)
> §§ 11 (tools), 12 (context management), 13 (citations), 17 (caching), 18 (PHI), plus Change
> Order 001 (the `research_log` addition).

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
