# Tyndale

Tyndale is an AI medical-billing advocate that audits both the provider's bill and the
insurer's EOB independently and never trusts either.

## Repo layout

This is a single monorepo (`tyndale.git`). Top-level areas:

| Path | What lives here |
|---|---|
| `intelligence-layer/` | Skills, subagent prompts, tool descriptions, reference rules, collection schemas, eval data (authored via Claude Code; does not deploy) |
| `runtime/` | FastAPI runtime — tool implementations, hook wiring, Postgres models, routes, crons |
| `apps/mobile/` | Expo React Native universal app (web + iOS + Android) — the product |
| `apps/web-marketing/` | Next.js marketing/SEO landing |
| `packages/shared/` | TypeScript types shared across the apps and the runtime API contracts |
| `infra/` | Terraform for Azure deployment (modules + per-env configs) |
| `docs/` | Decision log, integration contracts, and a reference copy of the full spec |
| `.github/` | CI workflows |

## Phase status

**Phase 0 closure complete** — monorepo skeleton, root configs, docs scaffold, integration
contracts published, and the source spec imported. **Phase 1 begins next** (foundation
files, frontend scaffold, runtime skeleton, and the Qdrant knowledge layer, in parallel).

## Quickstart

> The apps are empty scaffolds at Phase 0. The commands below are the intended workflow
> once Phase 1 lands code; they are placeholders for now.

```bash
# Clone
git clone git@github.com:thelittleguyai/tyndale.git
cd tyndale

# Node 20 (see .nvmrc)
nvm use

# Install JS/TS workspace dependencies (apps/* and packages/*)
npm install

# Run the apps (once they exist)
# npm run dev --workspace apps/mobile          # Expo universal app
# npm run dev --workspace apps/web-marketing    # Next.js marketing landing

# Runtime is a separate Python project (see runtime/ once scaffolded in Phase 1)
# cd runtime && <uv|poetry> install && <run command TBD>
```

## Where to look next

- **Product context, doctrines, and architecture:** [`CLAUDE.md`](CLAUDE.md)
- **Full source spec (54 + 7 imported documents):** [`docs/tyndale-spec/INDEX.md`](docs/tyndale-spec/INDEX.md)
- **Locked decisions:** [`docs/decision-log.md`](docs/decision-log.md)
- **Security/HIPAA interface contracts:** [`docs/integration-contracts.md`](docs/integration-contracts.md)
