# @tyndale/admin

Next.js 15 (App Router) admin console for Tyndale → **admin.tyndaleapp.net**. See
[`docs/admin-console.md`](../../docs/admin-console.md) for the full module reference.

## Routes
| Route | Module |
|---|---|
| `/` | Dashboard (CO-6A) |
| `/users`, `/users/[id]` | User management (CO-9 M1) |
| `/cases`, `/cases/[case_id]` | Case browse + comparison (CO-6A + CO-9 M3) |
| `/knowledge`, `/knowledge/[collection]`, `/knowledge/[collection]/[chunkId]` | RAG viewer (M2) |
| `/audit` | Audit log viewer (M4) |
| `/system`, `/system/crons/[name]` | System health + cron control (M5) |
| `/gaps` | Knowledge gap dashboard (M6) |

## Auth
Cookie-based — the `.tyndaleapp.net` session cookie carries from `admin.` → `api.`. The **runtime
is the source of truth**: non-admins get a 404 from `/v1/admin/*` (DL-60), which the UI renders as
a plain 404 (anti-enumeration). All API calls go through `src/lib/api-client.ts` with
`credentials: 'include'`.

## Local dev
```bash
npm install                          # from repo root (npm workspaces)
npm run dev -w @tyndale/admin        # NEXT_PUBLIC_RUNTIME_URL defaults to http://localhost:4000
npm run typecheck -w @tyndale/admin  # tsc --noEmit — the CI gate
```
Shared API types live in `@tyndale/shared` (`packages/shared/src/admin-types.ts`); the typed
client wrappers are in `src/lib/api-client.ts`.

> `npm run lint` (`next lint`) is not configured in this app (it drops into an interactive
> setup prompt) — `npm run typecheck` is the verification gate, matching the CI Typecheck workflow.
