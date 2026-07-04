# Tyndale Runtime

FastAPI monolith hosting the Claude Agent SDK orchestration, tool implementations, and the
hook lifecycle. This is a live service, not a skeleton: it runs the Lead Planner + subagent
audit against real Claude (via **Azure AI Foundry managed identity** — DL-79 — or a direct
Anthropic key / LiteLLM proxy), document ingestion + OCR, the three-number bill audit, the
chat surface (SSE streaming + persisted conversation store), magic-link auth, and the
intake / insurance-card flows. The four Claude Agent SDK hook surfaces are implemented
against `docs/integration-contracts.md`.

Feature flags gate the real integrations so the stack also runs fully offline for local dev
and tests (`USE_REAL_CLAUDE`, `USE_FOUNDRY`, `USE_REAL_OCR`); when they're off, deterministic
fixtures stand in. Schema is managed by Alembic (18+ migrations under `app/db/migrations`).

## Local dev

```bash
# With Docker (Postgres + runtime + LiteLLM):
docker compose up --build

# Or with uv directly against a local Postgres:
cp .env.example .env.local            # adjust DATABASE_URL if needed
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
uv run pytest
```

- Health: `GET /health` · Readiness (checks DB): `GET /readiness`
- Core API: `/v1/upload`, `/v1/audit`, `/v1/feedback`, `/v1/conversations` (+ SSE chat),
  `/v1/profile`, `/v1/insurance`, and the admin surface under `/v1/admin/*`

## Layout

- `app/config.py` — fail-fast env validation (Pydantic Settings)
- `app/agents/` — Claude Agent SDK orchestration (Lead Planner + subagents), runner, greeting
- `app/db/` — SQLAlchemy 2.0 models + Alembic migrations (schemas match the integration contracts)
- `app/hooks/` — contract models + implementations of the 4 SDK hooks + crisis classifier
- `app/routes/` — health/readiness + the `/v1/*` API (audit, chat, profile, admin console)
- `app/middleware/` — CORS, PHI-safe request logger, JSON error handler
- `app/stubs/` — deterministic fixtures + stubbed Claude/OCR (active while feature flags are off)
- `litellm/` — LiteLLM proxy config (optional Claude path alongside Foundry)
