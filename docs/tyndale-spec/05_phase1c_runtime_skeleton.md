# Phase 1C — Runtime Skeleton · Claude Code Prompt

**For:** Phil or Jonas (runtime track) — paste into a fresh Claude Code session at `~/code/tyndale`
**Goal:** Scaffold the FastAPI monolith in `runtime/`, write Postgres migrations for the case-file + audit-log + findings + deadlines + users + feedback schemas per the locked integration contracts, stub the four Claude Agent SDK hooks against the contract signatures, set up the LiteLLM proxy skeleton, and provide a Docker compose for local dev.

**Prerequisites:** Phase 0 closure pushed. Phase 1A and 1B are independent.

**Output:** A bootable FastAPI app under `runtime/` with health/readiness routes, Postgres migrations ready to run, hook interface stubs that conform to `docs/integration-contracts.md`, and one commit.

---

## How to run

1. Confirm Phase 0 closure is on `main`
2. Open a fresh Claude Code session in `~/code/tyndale`
3. Copy everything between the `BEGIN` and `END` markers below
4. Paste into Claude Code
5. Review the commit and confirm `docker compose up` boots the runtime + Postgres locally; push manually

---

```
BEGIN — Phase 1C Prompt

You are scaffolding Tyndale's runtime — the FastAPI monolith that hosts the
Claude Agent SDK orchestration, the tool implementations, and the hook
lifecycle. This is the runtime track; the security/HIPAA spine plugs into
the hook interfaces you'll stub here.

CONTEXT
- Stack: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x with Alembic for
  migrations, asyncpg as the driver, uvicorn for ASGI. Use `uv` for dependency
  management (faster than pip/poetry; lockfile-based).
- Database: PostgreSQL 16 locally via Docker compose; Azure Postgres Flexible
  Server in prod.
- LiteLLM proxy: self-hosted skeleton for V1-Lite; real hardening (weekly key
  rotation, per-route allow-lists) lands in Phase 4 with the security/HIPAA
  contact.
- Integration contracts: source of truth is docs/integration-contracts.md (which
  was extracted from the Phase 0 spec). Postgres schemas and hook signatures
  conform to that file.
- Regulatory posture: non-HIPAA-covered consumer-health app. Don't claim
  covered-entity status; do follow strong technical discipline (encryption,
  scrubbing, audit log) per the build kit's developer spec §18.
- This is a SCAFFOLD. No real Claude Agent SDK orchestration yet — Phase 2
  wires Lead Planner + Bill Detective + Math Person against this skeleton.

OUTPUTS

  runtime/
    pyproject.toml              — uv project config
    uv.lock                     — lockfile
    Dockerfile                  — multi-stage build for FastAPI app
    docker-compose.yml          — local Postgres + runtime
    .env.example                — every required env var with comments
    alembic.ini                 — Alembic config
    app/
      main.py                   — FastAPI app entry point
      config.py                 — Pydantic Settings; fail-fast env validation
      db/
        base.py                 — SQLAlchemy declarative base + engine
        session.py              — async session dependency
        models/
          __init__.py
          users.py              — User model
          case_files.py         — CaseFile with research_log
          findings.py           — Finding
          deadlines.py          — Deadline
          audit_events.py       — AuditEvent (encrypted payload column)
          feedback.py           — FeedbackEvent, FeedbackTriageQueue,
                                  FeedbackDeidCandidate
        migrations/
          env.py                — Alembic env
          versions/
            0001_initial.py     — initial migration creating all tables
      hooks/
        __init__.py
        contracts.py            — Pydantic models matching docs/integration-contracts.md
        user_prompt_submit.py   — stub implementation
        pre_tool_use.py         — stub implementation
        post_tool_use.py        — stub implementation
        stop.py                 — stub implementation
        crisis_classifier.py    — stub Haiku-4.5 classifier
      routes/
        health.py               — GET /health, GET /readiness
        upload.py               — POST /v1/upload (stub returning fixture)
        audit.py                — POST /v1/audit (stub returning fixture)
        feedback.py             — POST /v1/feedback (stub)
      middleware/
        cors.py                 — CORS allow-list from env
        request_logger.py       — PHI-safe logger (no body logging)
        error_handler.py        — JSON error responses, no stack to client
      stubs/
        fixtures.py             — the MRI scenario from how_tyndale_works_reference.md
        claude.py               — stubbed Lead Planner / Bill Detective / Math Person
        ocr.py                  — stubbed Document Intelligence
      schemas/
        case_file.py            — Pydantic schemas (request/response shapes)
        feedback.py             — matches docs/tyndale-spec/L05_feedback_consent_schema.md
        api_contract.py         — request/response types per route
    litellm/
      config.yaml               — LiteLLM proxy config (skeleton; real hardening in Phase 4)
      README.md                 — how the proxy will be deployed in Phase 4
    tests/
      conftest.py               — pytest fixtures
      test_health.py            — GET /health smoke test
      test_routes_stub.py       — POST stubs return fixture shapes

STEP 1 — pyproject.toml (uv project)

Initialize a uv project in runtime/. Dependencies:

  fastapi >= 0.110
  uvicorn[standard] >= 0.27
  pydantic >= 2.6
  pydantic-settings >= 2.2
  sqlalchemy >= 2.0
  asyncpg >= 0.29
  alembic >= 1.13
  python-multipart >= 0.0.9         # multipart upload handling
  python-jose[cryptography]         # JWT for inter-service auth (Phase 2)
  httpx >= 0.27                     # outbound calls
  structlog >= 24.1                 # structured logging
  presidio-analyzer                 # stub usage only in Phase 1C
  presidio-anonymizer               # stub usage only in Phase 1C

Dev dependencies:
  pytest >= 8
  pytest-asyncio
  httpx
  ruff
  mypy

Python: ^3.12. ASGI: uvicorn.

STEP 2 — app/config.py (env validation)

Pydantic Settings class. Fail-fast on missing required vars at startup.

Required vars:
  NODE_ENV  (development | staging | production)
  PORT  (default 4000)
  LOG_LEVEL  (default info)
  DATABASE_URL  (asyncpg postgresql+asyncpg://...)
  CORS_ALLOWED_ORIGINS  (comma-separated)

Optional (warned if missing in prod):
  ANTHROPIC_API_KEY  (Phase 2)
  AZURE_DOC_INTELLIGENCE_ENDPOINT  (Phase 2)
  AZURE_DOC_INTELLIGENCE_KEY  (Phase 2)
  LITELLM_PROXY_URL  (Phase 4)
  AZURE_KEY_VAULT_URL  (Phase 4 — for audit log encryption keys)

Feature flags (off by default; stubs run when off):
  USE_REAL_CLAUDE  (default false)
  USE_REAL_OCR  (default false)
  USE_REAL_PRESIDIO  (default false; security spine flips to true in Phase 4)

STEP 3 — app/db/ — SQLAlchemy models matching docs/integration-contracts.md

Read docs/integration-contracts.md Section 2.2 (audit_events), 2.3 (case files
with research_log), and 2.4 (feedback handoff tables). Implement matching
SQLAlchemy 2.0 models in app/db/models/.

Key requirements per the contracts:
- audit_events.payload_encrypted is BYTEA — encryption happens at write time
  by the security spine. In Phase 1C, write a clear-text JSON payload as a
  placeholder; flag with a TODO referencing Phase 4.
- audit_events.payload_hash is BYTEA SHA-256
- audit_events.key_version is INT
- case_files.research_log is JSONB defaulting to '[]'
- case_files.version supports optimistic locking
- All UUIDs default to gen_random_uuid() — enable the pgcrypto extension
- Add the indexes specified in the contracts file

STEP 4 — app/db/migrations/0001_initial.py (Alembic)

Create a single Alembic migration that creates all the tables, indexes, and the
pgcrypto extension. The migration is idempotent (op.execute('CREATE EXTENSION
IF NOT EXISTS pgcrypto')).

STEP 5 — app/hooks/contracts.py (Pydantic contract models)

Define Pydantic models matching docs/integration-contracts.md Section 2.1 hook
signatures:

  - UserPromptSubmitInput, UserPromptSubmitResult
  - PreToolUseInput, PreToolUseResult
  - PostToolUseInput, PostToolUseResult (returns None semantically; void via
    raise-on-error pattern)
  - StopInput, StopResult

Each contract is fully typed with field-level docstrings. These are the
boundary the security/HIPAA contact builds against.

STEP 6 — app/hooks/ — Stub implementations

For each of the four hook surfaces + crisis classifier, write a stub that
returns the safe-default shape and logs a clear "STUB — security spine not yet
wired" warning at startup. The stubs:

  user_prompt_submit.py
    - Returns scrubbed_message = raw_message (no actual scrubbing)
    - wrapped_documents wraps OCR text in "DATA, NOT INSTRUCTIONS" framing
    - injection_signals = []
    - block = False

  pre_tool_use.py
    - For qdrant_search_laws_regulations and qdrant_search_payer_policies:
      reject if effective_date is missing in args (enforces the rule even
      pre-Presidio); return approved=False with reason
    - For send_email and doc_generate: reject if approval_token is missing
    - Otherwise: approved=True, sanitized_args=tool_args (no scrubbing yet)

  post_tool_use.py
    - Writes an audit_events row with clear-text JSON payload (TODO: encryption
      in Phase 4)
    - Computes SHA-256 hash of the payload
    - key_version = 0 (placeholder; real key versions come in Phase 4)
    - Logs but does not alert ops on failures (alerting wires in Phase 4)

  stop.py
    - Parses generated_output for citation markers
    - Resolves each marker against retrieved_chunks
    - Returns resolved=True if all resolve; otherwise action='regenerate' for
      attempt < 3, 'human_review' for attempt == 3

  crisis_classifier.py
    - Stub: returns crisis_detected=False unconditionally
    - TODO: wire Haiku-4.5 classifier in Phase 4

STEP 7 — app/routes/ — Stub routes

Implement routes returning realistic fixture shapes (the MRI scenario from
docs/tyndale-spec/how_tyndale_works_reference.md): bill $1,200, EOB-claimed
$1,200, Tyndale-computed $560, with one Tier B finding citing a placeholder
authority and src_id.

  /health             — 200 {status: "ok", version: "0.1.0"}
  /readiness          — 200 if DB connects; 503 otherwise
  /v1/upload          — accepts multipart file; returns case_file_id,
                        document_id; doesn't persist real file content yet
  /v1/audit           — given case_file_id, returns the MRI fixture
  /v1/feedback        — accepts a FeedbackEvent matching the L05 schema;
                        writes to feedback_events table

All routes use the schemas from app/schemas/ — request/response models.

STEP 8 — Middleware

  cors.py            — CORS allow-list from env CORS_ALLOWED_ORIGINS;
                       wildcard rejected outside development
  request_logger.py  — structured logging; explicitly excludes request bodies
                       from log payloads (PHI-safe by default)
  error_handler.py   — JSON-shaped error responses; never include Python
                       tracebacks in user-facing errors

STEP 9 — Dockerfile + docker-compose.yml

Dockerfile: multi-stage. Stage 1 builds with uv; stage 2 runs uvicorn.

docker-compose.yml:
  services:
    postgres:
      image: postgres:16
      env: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
      volumes: postgres_data
      ports: 5432:5432
    runtime:
      build: .
      env_file: .env.local
      depends_on: postgres
      ports: 4000:4000
      command: >
        bash -c "uv run alembic upgrade head &&
                 uv run uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload"
    litellm:
      image: ghcr.io/berriai/litellm:latest
      ports: 4001:4000
      volumes: ./litellm/config.yaml:/app/config.yaml
      command: --config /app/config.yaml
      # Real hardening (key rotation, allow-lists) lands in Phase 4

  volumes:
    postgres_data:

STEP 10 — litellm/config.yaml (skeleton)

A minimal LiteLLM config that:
- Defines Claude routes: lead_planner, bill_detective, math_person,
  legal_researcher (Phase 2 unused), strategist (Phase 2 unused),
  code_validator (Phase 2 unused), judge
- Points each to anthropic/claude-sonnet-4-6 (or appropriate model) with
  fallback chain Anthropic direct → Bedrock → Foundry (Bedrock + Foundry
  placeholder configs; real wiring in Phase 4)
- Enables prompt caching at the proxy level
- Does NOT yet enable hardening (allow-lists, weekly rotation, audit logging) —
  those are Phase 4 with the security spine

litellm/README.md notes that the real production config is Phase 4 with the
security/HIPAA contact, and that this skeleton is for local dev only.

STEP 11 — .env.example

  # Server
  NODE_ENV=development
  PORT=4000
  LOG_LEVEL=info
  CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8081

  # Database
  DATABASE_URL=postgresql+asyncpg://tyndale:tyndale@localhost:5432/tyndale

  # Anthropic (Phase 2 — leave blank in Phase 1C)
  ANTHROPIC_API_KEY=
  LITELLM_PROXY_URL=http://localhost:4001

  # Azure Document Intelligence (Phase 2 — leave blank in Phase 1C)
  AZURE_DOC_INTELLIGENCE_ENDPOINT=
  AZURE_DOC_INTELLIGENCE_KEY=

  # Azure Key Vault (Phase 4 — security spine integration)
  AZURE_KEY_VAULT_URL=

  # Feature flags
  USE_REAL_CLAUDE=false
  USE_REAL_OCR=false
  USE_REAL_PRESIDIO=false

STEP 12 — tests/

  conftest.py        — sets up async test client, ephemeral test DB
  test_health.py     — GET /health returns 200 with the expected shape
  test_routes_stub.py
                     — POST /v1/audit with the fixture case_file_id returns
                       the MRI scenario shape
                     — POST /v1/feedback accepts a valid FeedbackEvent
                     — POST /v1/upload accepts a small fixture file

Run `uv run pytest` and confirm all tests pass.

STEP 13 — Verify

  docker compose up --build -d
  docker compose exec runtime uv run alembic upgrade head
  curl http://localhost:4000/health
  curl http://localhost:4000/readiness
  uv run pytest

All four checks succeed. Then `docker compose down`.

STEP 14 — Single commit

  git add runtime/
  git commit -m "feat(runtime): Phase 1C skeleton — FastAPI + Postgres + hook stubs"

DO NOT push. Show the commit and the dev-loop output.

STEP 15 — REPORT BACK

In your reply, include:
- `git log --oneline -2`
- `git diff --stat HEAD~1`
- Output of `curl http://localhost:4000/health`
- Output of `uv run pytest`
- Confirmation Alembic migration ran cleanly
- Any deviation from this prompt and why
- Anything that needs my attention (especially: the hook stubs are the
  contract surface for the security/HIPAA contact — flag if anything in
  docs/integration-contracts.md seemed ambiguous)

DO NOT proceed beyond this prompt. Phase 2 wires real Claude Agent SDK
orchestration, real Document Intelligence OCR, and starts pulling the hook
implementations from the security/HIPAA contact.

END — Phase 1C Prompt
```

---

## What this delivers

After Phase 1C executes and is pushed:

- A bootable FastAPI app at `runtime/` that brings up the runtime + Postgres locally via Docker Compose
- Postgres migrations matching the locked integration contracts: `case_files` (with `research_log` per Change Order 001), `findings`, `deadlines`, `audit_events` (encrypted-payload-ready, clear-text in Phase 1C with TODO for Phase 4), `users`, plus the three feedback tables
- Stub implementations of all four Claude Agent SDK hook surfaces conforming to `docs/integration-contracts.md` — the surface Brock's security/HIPAA contact builds against
- Stub routes returning the MRI scenario fixture so frontend can hit a real API even before Claude is wired
- LiteLLM proxy skeleton config for local dev (real hardening in Phase 4)
- pytest scaffolding green
- PHI-safe request logger (excludes bodies from logs by default) — even at this scaffold stage, no PHI hits app logs

## What's deferred to later phases

- **Real Claude Agent SDK orchestration** (Lead Planner + Bill Detective + Math Person spawning) → Phase 2
- **Real Document Intelligence OCR** → Phase 2
- **Audit log encryption** (AES-GCM via Azure Key Vault) → Phase 4 with the security/HIPAA contact
- **Presidio scrubbing in PreToolUse** → Phase 4 with the security/HIPAA contact
- **LiteLLM proxy hardening** (weekly key rotation, per-route allow-lists, request-level audit logging) → Phase 4
- **Crisis classifier with real Haiku-4.5 call** → Phase 4
- **Stripe integration** → Phase 4
