# Tyndale Runtime (Phase 1C skeleton)

FastAPI monolith that will host the Claude Agent SDK orchestration, tool implementations, and
the hook lifecycle. This is the **Phase 1C scaffold** — no real Claude orchestration, OCR, or
PHI scrubbing yet (those land in Phases 2 and 4). The four Claude Agent SDK hook surfaces are
**stubbed** against `docs/integration-contracts.md`; the security/HIPAA contact implements
against those contracts.

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
- Stub API: `POST /v1/upload`, `POST /v1/audit`, `POST /v1/feedback`

## Layout

- `app/config.py` — fail-fast env validation (Pydantic Settings)
- `app/db/` — SQLAlchemy 2.0 models + Alembic migrations (schemas match the integration contracts)
- `app/hooks/` — contract models + stub implementations of the 4 SDK hooks + crisis classifier
- `app/routes/` — health/readiness + stubbed `/v1/*` endpoints returning the MRI fixture
- `app/middleware/` — CORS, PHI-safe request logger, JSON error handler
- `app/stubs/` — fixtures + stubbed Claude/OCR (active while feature flags are off)
- `litellm/` — LiteLLM proxy skeleton (real hardening in Phase 4)
