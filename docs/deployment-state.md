# Tyndale — Dev Deployment & Auth State (Cowork sync)

**Last updated:** 2026-05-30 · **Branch:** `main` · **HEAD:** `b38e27f`

This doc is the source of truth for *what is deployed in dev, how auth works, and
the gotchas learned the hard way*. Read it before touching infra, auth, or the
mobile/web build. Pairs with `docs/decision-log.md` (DL-01–DL-45) and
`docs/integration-contracts.md`.

---

## 1. TL;DR — what's live

Real auth + the full product loop are **deployed and working** in dev on three
public HTTPS subdomains of `tyndaleapp.net` (Azure-authoritative DNS, managed TLS):

| URL | What | Container App | CAE |
|---|---|---|---|
| `https://dev.tyndaleapp.net` | Marketing landing + `/signin` + `/signed-in` (Next.js 15) | `tyndale-dev-marketing` | external |
| `https://app.tyndaleapp.net` | **The product** — dashboard/upload/cases/settings/admin (Expo web export, nginx) | `tyndale-dev-app` | external |
| `https://api.tyndaleapp.net` | Runtime API (FastAPI) — `/v1/*`, `/health`, `/v1/auth/*` | `tyndale-dev-runtime` | external |

Flow that works end-to-end: **sign in** (Google or email magic-link) on
`dev.` or `app.` → runtime sets a `.tyndaleapp.net` session cookie → redirected to
`app.tyndaleapp.net` → dashboard renders with the user's real data.

`USE_REAL_AUTH=true` is **live** — the runtime enforces real sessions (no more
seeded-admin stub in dev).

---

## 2. Azure infrastructure (dev)

- **Subscription** `0ef28be6-6b19-4d6f-a83f-bdb4324f941d` · **tenant** `f55c1074-…` · **region** `centralus` · **RG** `tyndale-dev-rg`
- **DNS:** zone `tyndaleapp.net` is Azure-authoritative (registrar NS → Azure DNS). Records: `dev`, `app`, `api` CNAMEs + matching `asuid.*` TXT for cert validation.
- **VNet** `tyndale-dev-vnet` with subnets: container-apps (internal CAE), container-apps-ext (external CAE), postgres (delegated).
- **Two Container Apps Environments (both in the same VNet):**
  - `tyndale-dev-cae` — **internal** (VNet-only). Hosts: `litellm`, `qdrant`, and the migrations **Job** (`tyndale-dev-runtime-migrations`).
  - `tyndale-dev-cae-external` — **public**. Hosts: `marketing`, `runtime`, `app`.
  - The runtime was **moved** internal→external so it can have a public ingress for browser auth (DL-42). It still reaches the VNet-only Postgres + internal qdrant/litellm over the shared VNet.
- **Postgres** `tyndale-dev-postgres-flex-71izsy` (Flexible, VNet-only). DB `tyndale`. `azure.extensions` allows `pgcrypto`.
- **Key Vault** `tyndale-dev-kv-71izsy`. Secrets: `ANTHROPIC-API-KEY`, `VOYAGE-API-KEY`, `GOOGLE-OAUTH-CLIENT-ID/SECRET`, `NEXTAUTH-SECRET`, `AUTH-SECRET` (auto-generated), `SENDGRID-API-KEY` (Phil-supplied), `AZURE-DOC-INTELLIGENCE-KEY`, `POSTGRES-ADMIN-PASSWORD`, `DATABASE-URL`.
- **Doc Intelligence** `tyndale-dev-doc-intel`. **App Insights** + **Log Analytics** wired.
- **Scale:** `marketing`, `runtime`, `app` are `min_replicas=1` (kept warm — avoids 20–30s cold starts). `litellm`, `qdrant` stay scale-to-zero (only hit during the audit flow).

Everything is Terraform (`infra/envs/dev/`). Real values + phased toggles live in
`infra/envs/dev/terraform.tfvars` (gitignored); `terraform.tfvars.example` documents them.

---

## 3. Auth architecture (Phase 2K, live)

- **Runtime owns auth.** It mints/verifies a session JWT (HS256, signed by `AUTH_SECRET`) and issues it as a cookie. Two ways in:
  - **Google OAuth** — runtime builds the consent URL with redirect `https://api.tyndaleapp.net/v1/auth/callback` (registered in the Google console for client `496221857458-…`).
  - **Email magic-link** — runtime emails a one-time link via SendGrid; single-use (jti recorded in `magic_link_consumed`, migration 0005).
- **Session cookie:** `tyndale_session`, **HttpOnly + Secure + SameSite=Lax**, `domain=.tyndaleapp.net`. `dev.`/`app.`/`api.` are the *same site* (registrable domain `tyndaleapp.net`), so the cookie is shared across all three and Lax survives the OAuth redirect.
- **CORS:** runtime allows `https://dev.tyndaleapp.net` + `https://app.tyndaleapp.net` **with credentials**.
- **match-on-verified-email:** a verified email maps to one user row (case-insensitive); the seeded `pfluegelcx@gmail.com` row (`user_type=admin`) is found, not duplicated.
- **Post-login:** `AUTH_SUCCESS_REDIRECT=https://app.tyndaleapp.net` → sign-in lands directly on the dashboard (skips the marketing `/signed-in` interstitial).
- **NOT implemented:** Sign in with Apple (required by App Store Guideline 4.8 before iOS submission). Rate limiter is per-replica in-memory (→ Redis at Phase 4).

---

## 4. CI/CD

GitHub Actions, OIDC federation to Azure (`AZURE_CLIENT_ID/TENANT_ID/SUBSCRIPTION_ID`
secrets, `dev` environment), images to **public GHCR** (`ghcr.io/thelittleguyai/tyndale/*`).

| Workflow | Trigger (paths) | Does |
|---|---|---|
| `deploy-runtime.yml` | `runtime/**`, `packages/shared/**` | build runtime image → **run migrations Job (alembic upgrade head + seed), gated** → roll runtime CA |
| `deploy-web-marketing.yml` | `apps/web-marketing/**`, `packages/shared/**` | build (with `NEXT_PUBLIC_RUNTIME_URL` build-arg) → roll marketing CA |
| `deploy-app.yml` | `apps/mobile/**`, `packages/shared/**` | build Expo static export (with `EXPO_PUBLIC_API_BASE_URL` build-arg) → roll app CA |
| `typecheck.yml` | push | mobile + web typecheck + barrel-export completeness |

- **Migrations run in CI** before the runtime rolls; `0005` = `magic_link_consumed`. Seed creates the admin user `pfluegelcx@gmail.com`.
- **`NEXT_PUBLIC_*` / `EXPO_PUBLIC_*` are baked at BUILD time** (Docker build-args), **not** Container App env vars — a runtime env var is too late.

---

## 5. What shipped this session (newest first)

```
b38e27f fix(app): dashboard 401 (send cookie) + header nav + admin page + no-cache HTML + skip signed-in interstitial
fc4d71f fix(app): dedupe React in the Metro web bundle (fixes app.tyndaleapp.net white screen)
b7f78b6 fix(app): web-safe session store (un-blank app.tyndaleapp.net) + keep apps warm
11f9be3 feat(app): deploy Expo web app to app.tyndaleapp.net
fcadc30 docs: DL-42 — runtime is a public API at api.tyndaleapp.net
a32537f feat(infra+web): expose runtime at api.tyndaleapp.net for real auth
b92f5df feat(infra): wire runtime AUTH_SECRET + optional SendGrid + use_real_auth toggle
bf21a53 feat(auth): Phase 2K — real Google + email magic-link auth + typecheck CI
```

Arc: Phase 2K built the auth code → wired `AUTH_SECRET`/SendGrid as IaC → exposed
the runtime publicly at `api.` → deployed the product app at `app.` → then fixed a
chain of web-only runtime bugs (white screen, 401s) surfaced by live testing.

---

## 6. Hard-won gotchas (do not re-hit these)

1. **React must be deduped at Metro, not npm (DL-44).** Two React copies (mobile pins 19.0.0, web-marketing floats 19.2.x) → `Cannot read properties of null (reading 'useState')` → white screen. Fixed via `apps/mobile/metro.config.js` `resolveRequest`. **Never run a clean `npm install`** — `react-native-worklets@0.9.1` peers RN `0.83–0.86` vs our `0.79.6` → **ERESOLVE**. Use `npm ci` (committed lockfile) only.
2. **All app→API calls need `credentials:'include'` (DL-45).** Cross-subdomain cookie. Route through `cfetch()` in `apps/mobile/lib/api-client.ts`. A missing one = silent `401 "not authenticated"`.
3. **SPA HTML must be `no-cache` (DL-45).** nginx caches `/_expo` + `/assets` immutably but `Cache-Control: no-cache` for HTML, or browsers serve a stale `index.html` pointing at deleted chunk hashes after each deploy.
4. **`expo-secure-store` has no web impl** — importing it at module load white-screens web. Platform-split: `lib/session-store.ts` (native) + `lib/session-store.web.ts` (localStorage shim).
5. **`NEXT_PUBLIC_*` / `EXPO_PUBLIC_*` are build-time** — pass as Docker `--build-arg`, not CA env.
6. **A Container App env/CAE change that *replaces* the CA reverts to the placeholder image** (`ignore_changes=[image]` only suppresses drift, not creation) → must re-roll via CI/`az containerapp update` after.
7. **Scale-to-zero = 20–30s cold starts.** User-facing CAs are `min_replicas=1`.
8. **DNS negative caching** — browsers/resolvers cache `NXDOMAIN`; after creating a subdomain, a hard-refresh / `dscacheutil -flushcache` may be needed locally even though Azure's authoritative NS already answers.
9. **Migration saga (earlier, resolved):** 5 stacked bugs — tenant mismatch, unregistered `Microsoft.Storage` RP, `@`/`:` in DB password (urlencode), Alembic `versionless_id`, wrong `az job execution` poll flags (masked failures), `pgcrypto` not allow-listed via `azure.extensions`.

---

## 7. Open items / next

- **Sign in with Apple** — App Store Guideline 4.8; needed before iOS submission.
- **Runtime network hardening** — it's now a public authed API; rate limits / IP rules / WAF deferred.
- **Rate limiter → Redis** (currently per-replica in-memory) — Phase 4.
- **SendGrid BAA** (DL-18) before any real PHI-adjacent email; sender `no-reply@tyndaleapp.net` is verified.
- **Security spine still STUB** in the runtime (Presidio PHI scrubbing, UserPromptSubmit/Stop hooks, crisis classifier, encrypted audit log) — owned by a separate contact per CLAUDE.md / `integration-contracts.md`.
- **Real Claude/Anthropic + qdrant/litellm** audit path: works behind fixtures; first live audit will cold-start litellm/qdrant.

---

## 8. Operating notes (for whoever drives next)

- Infra: `cd infra/envs/dev && terraform plan/apply` (uses gitignored `terraform.tfvars`). Phased domain/cert toggles must stay `true` in tfvars or a re-apply will detach domains.
- Deploys: push to `main` (path-filtered) or `gh workflow run <deploy-*.yml>`.
- Logs: `az containerapp logs show -n tyndale-dev-runtime -g tyndale-dev-rg --revision <rev>` (runtime is public; `/health` is the quick check). Internal CAE resources aren't reachable from outside the VNet.
- Conventions (unchanged): one commit per phase; **do not push unless asked**; lockfiles committed; DL entries appended chronologically (now **DL-45**); commit trailer present.
