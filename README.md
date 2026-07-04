# Tyndale

Tyndale is an AI medical-billing advocate that audits both the provider's bill and the
insurer's EOB independently and never trusts either.

## Repo layout

This is a single monorepo (`tyndale.git`). Top-level areas:

| Path | What lives here |
|---|---|
| `intelligence-layer/` | Skills, subagent prompts, tool descriptions, reference rules, collection schemas, eval data (authored via Claude Code; does not deploy) |
| `runtime/` | FastAPI runtime — Claude Agent SDK orchestration, tool implementations, hook wiring, Postgres models + Alembic migrations, routes, crons |
| `apps/mobile/` | Expo React Native universal app (web + iOS + Android) — the member-facing product |
| `apps/admin/` | Next.js admin console — case browse/detail, provenance, verdict capture, user management, knowledge browser, system health (IP-allowlisted) |
| `apps/web-marketing/` | Next.js marketing/SEO landing |
| `packages/shared/` | TypeScript types shared across the apps and the runtime API contracts |
| `infra/` | Terraform for Azure deployment (modules + per-env configs, incl. AI Foundry) |
| `docs/` | Decision log, integration contracts, and a reference copy of the full spec |
| `.github/` | CI workflows |

## Status

Live product, not a scaffold. The runtime serves real magic-link auth, the Claude
Agent SDK orchestration (Lead Planner + subagents) running against Claude via **Azure
AI Foundry managed identity** (no API key in prod — DL-79), the four SDK hook surfaces,
document ingestion + OCR, the three-number bill audit, a chat surface with SSE
streaming and a persisted conversation store, and the intake/onboarding + insurance-card
flows. Data lives in Postgres across 18+ Alembic migrations. Two front-ends ship on top:
the Expo member app (`apps/mobile`) and the admin console (`apps/admin`).

Fixture fallbacks and feature flags still gate some paths for local dev and tests
(`USE_REAL_CLAUDE`, `USE_FOUNDRY`, `USE_REAL_OCR`), so the stack also runs end-to-end
offline. See [`docs/decision-log.md`](docs/decision-log.md) for the locked decisions
behind the current architecture.

## Quickstart

```bash
# Clone
git clone git@github.com:thelittleguyai/tyndale.git
cd tyndale

# Node 20 (see .nvmrc)
nvm use

# Install JS/TS workspace dependencies (apps/* and packages/*)
npm install

# Run the apps
npm run dev --workspace apps/mobile          # Expo universal app (web + iOS + Android)
npm run dev --workspace apps/admin           # Next.js admin console
npm run dev --workspace apps/web-marketing   # Next.js marketing landing

# Runtime is a separate Python project (uv) — see runtime/README.md
# cd runtime && uv sync && uv run alembic upgrade head && \
#   uv run uvicorn app.main:app --port 4000 --reload
```

## Where to look next

- **Product context, doctrines, and architecture:** [`CLAUDE.md`](CLAUDE.md)
- **Full source spec (54 + 7 imported documents):** [`docs/tyndale-spec/INDEX.md`](docs/tyndale-spec/INDEX.md)
- **Locked decisions:** [`docs/decision-log.md`](docs/decision-log.md)
- **Security/HIPAA interface contracts:** [`docs/integration-contracts.md`](docs/integration-contracts.md)
