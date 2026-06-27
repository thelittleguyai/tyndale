# Tyndale Decision Log

Every locked decision from the parent build plan and the Phase 0 spec, recorded with date
and owner. This is searchable history, not a research paper — one paragraph of reasoning per
entry. New decisions append here as `DL-NN`. Status updates on the out-of-Cowork parallel
tracks (counsel, BAAs, licensing, Azure tenancy) flow through Brock and are recorded here as
they land.

---

## DL-01 — V1-Lite ships first, Full V1 immediately after
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Build and launch V1-Lite — a forward-compatible subset with a 3-agent
intelligence layer and document upload — first, then begin the Full V1 expansion immediately
on V1-Lite launch.
**Reasoning:** V1-Lite proves the core audit brain end-to-end while deferring the heavier
FHIR and letter-generation surface. Because V1-Lite's contracts (case-file schema, citation
format, voice tiering, tool return shapes) are Full V1's contracts, the upgrade is expansion,
not rewrite — and the feedback loop running from day one generates the labels that train
Full V1.
**Reversibility:** locked

## DL-02 — Single brand with beta framing
**Date:** 2026-05-27
**Decided by:** Brock (from docs, reaffirmed)
**Decision:** Ship under a single brand, "Tyndale," with explicit beta framing, rather than
splitting V1-Lite and Full V1 into separate products or brands.
**Reasoning:** One brand keeps the consumer story simple and carries V1-Lite users straight
into Full V1; beta framing sets accurate expectations during the limited-capability launch
window.
**Reversibility:** locked

## DL-03 — National launch, all 50 states
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Launch nationally across all 50 states rather than piloting in a subset.
Tier-1 commercial payers at V1-Lite: UnitedHealthcare, Anthem, Aetna, Cigna, BCBS, Humana,
Kaiser. Medicare/Medicaid deferred to Full V1.
**Reasoning:** The federal-law layer (ACA, ERISA, NSA) plus the State-Specific Rights
Addendum covers the legal surface, and the Tier-1 payers are national — so a single-state
pilot would add gating without reducing legal complexity.
**Reversibility:** locked

## DL-04 — Crisis decline with no routing of any kind, reaffirmed
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Mental-health crisis input gets a clean decline with no 988 referral and no
routing of any kind; a Haiku 4.5 classifier screens input ahead of normal processing and
triggers the decline immediately, bypassing the Lead Planner.
**Reasoning:** Tyndale is a medical-billing advocacy/reconciliation platform, not a crisis
center, and the brand claims authority only over what it itself handles. Brock reaffirmed
this deliberately; it is the most-disputed category in the design (no-988 is unusual for
consumer AI), so a single pre-launch revisit is noted, but the default stands.
**Reversibility:** locked (one pre-launch revisit noted)

## DL-05 — Non-HIPAA-covered consumer-health-app posture
**Date:** 2026-05-27
**Decided by:** Brock (pending counsel confirmation)
**Decision:** Tyndale ships as a non-HIPAA-covered consumer-health app governed by the FTC
Act, the FTC Health Breach Notification Rule, and state privacy/health-data laws — not as a
covered entity or business associate.
**Reasoning:** The user voluntarily uploads their own documents for their own benefit, which
generally keeps the app outside HIPAA coverage. Technical discipline (encryption, PHI
scrubbing, audit log, vendor BAAs) is unchanged because the data is still sensitive and state
laws (e.g., Washington MHMDA, California sensitive-PI) are stringent; only the framing
changes. Counsel must reconfirm in writing before launch, and Full V1's 1upHealth
integration triggers a HIPAA re-look.
**Reversibility:** revisable with cause (pending counsel confirmation; 1upHealth re-look)

## DL-06 — Tech stack: React Native + Expo (universal) + Next.js marketing landing
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** React Native + Expo as a universal codebase (web + iOS + Android via Expo
Router) for the product, with a small sibling Next.js project for the marketing/SEO landing.
**Reasoning:** One codebase across web and native minimizes duplicated product surface for a
small team; Next.js is kept only for the static marketing landing where SEO matters. Phil
owns the stack decision and will ramp on RN with team support.
**Reversibility:** locked
**Narrowed by:** DL-48 — native iOS and Apple Developer enrollment deferred indefinitely;
web-only at app.tyndaleapp.net is the V1-Lite product surface.

## DL-07 — Single monorepo in tyndale.git
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** All code lives in a single monorepo, `tyndale.git`, with a subtree layout
(`intelligence-layer/`, `runtime/`, `apps/*`, `packages/shared/`, `infra/`).
**Reasoning:** A monorepo is the single source of truth for V1-Lite contracts — a TypeScript
type change in `packages/shared` type-checks across mobile and web-marketing instantly, and
the runtime references the same contracts. Apps stay decoupled at deploy time even while
coupled at the contract level.
**Reversibility:** locked

## DL-08 — Walking-skeleton build sequencing
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** Build a thin end-to-end walking skeleton first, then thicken each layer;
owners (Phil/Jonas/Josh/Brock) work in parallel after Phase 1.
**Reasoning:** A thin end-to-end path surfaces integration risk early and gives every track a
real contract to build against, instead of completing layers in isolation and discovering
mismatches late.
**Reversibility:** locked

## DL-09 — Plausible for analytics; no advertising/retargeting trackers anywhere
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** Use Plausible for first-party, privacy-respecting analytics; no advertising or
retargeting trackers anywhere in the product.
**Reasoning:** A consumer-health app handling billing data cannot carry ad/retargeting
trackers without undermining its privacy posture and state-law compliance. Plausible is
cookieless (no GDPR banner needed) and sufficient for V1-Lite traffic; a pre-launch DOM audit
confirms no trackers reached health/billing pages.
**Reversibility:** locked

## DL-10 — Free-tier abuse controls: email + phone verification + Terms Section 8
**Date:** 2026-05-27
**Decided by:** Phil (CTO)
**Decision:** Guard the free tier (one bill analysis) with email (via Google) + phone
verification at signup, backed by Terms Section 8's explicit prohibition on multi-account
evasion.
**Reasoning:** The free tier invites multi-account abuse; verification at signup plus
contractual suspension power is the lightest control that meaningfully raises the cost of
evasion without burdening legitimate users.
**Reversibility:** locked

## DL-11 — Security/HIPAA infrastructure built by Brock's contact, tracked outside this plan
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** The security/HIPAA spine (Presidio scrubbing, encrypted audit log, key
rotation, prompt-injection + citation hooks, crisis classifier, LiteLLM proxy hardening,
email approval gate, BAA chain) is built by Brock's contact and tracked outside Cowork's
plan; Cowork specifies integration contracts only.
**Reasoning:** The security work is specialized and runs on its own schedule. Isolating it
behind a stable interface (`docs/integration-contracts.md`) lets the rest of the team build
against contracts without owning the implementation, and keeps the sensitive spine with a
dedicated owner.
**Reversibility:** locked

## DL-12 — Apple Sign-In: fast-follow at native iOS submission, not V1-Lite web launch
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** V1-Lite web launches with Google + Email sign-in; Apple Sign-In stands up in
parallel during Phases 2–4 and ships with the native iOS App Store submission, not the
V1-Lite web launch.
**Reasoning:** Apple Sign-In is required by App Store policy for native iOS but not for the
web launch; deferring it to the iOS submission removes it from the web-launch critical path
while still landing before the native app needs it.
**Reversibility:** locked
**Superseded by:** DL-48 — Apple Developer enrollment = NO; Phase 3 (mobile/iOS/Apple
Sign-In) dropped from the Cowork queue.

## DL-13 — Change Order 001 (4 behavioral additions) accepted into V1-Lite
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Accept Change Order 001's four behavioral additions into V1-Lite scope: an
always-loaded behavioral core, an enumerated proactive thinking loop, lead-with-status on app
open, and a `research_log` field on the case file.
**Reasoning:** All four are additive and forward-compatible — they sharpen the "thinks five
steps ahead" promise and the audit discipline without changing contracts. The `research_log`
in particular implements the "what do I now know?" step the Lead Planner reads before
re-investigating.
**Reversibility:** locked

## DL-14 — Post-V1-Lite agent-company vision parked
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Park the "Tyndale as a small AI agent company" north-star (six agent tiers, QA
agent, Compliance Scanner); revisit after Full V1 stabilizes.
**Reasoning:** The vision is a backlog north-star, not launch-critical, and no V1-Lite work
touches it. The strongest first additions (QA agent, Compliance Scanner) are revisited only
once Full V1 is stable so they build on a settled foundation.
**Reversibility:** revisable with cause (revisit after Full V1 stabilizes)

## DL-15 — Legal entity is The Little Guy LLC d/b/a Tyndale (Utah); governing law Utah
**Date:** 2026-05-27
**Decided by:** Brock (per legal pack)
**Decision:** The operating entity is The Little Guy LLC d/b/a Tyndale (Utah-based);
governing law is Utah.
**Reasoning:** Per the legal pack. Fixes the entity and forum for the Terms, Privacy Policy,
and the binding-arbitration / class-waiver provisions.
**Reversibility:** locked

## DL-16 — Pricing locked
**Date:** 2026-05-27
**Decided by:** Brock (per legal pack)
**Decision:** $11.99/month or $100/year for unlimited use; the free tier is one bill
analysis; subscriptions cancel at the end of the current period with no prorated refunds.
**Reasoning:** Per the legal pack. A flat unlimited price keeps the consumer offer simple;
the single free analysis demonstrates value while capping abuse (see DL-10); end-of-period
cancellation with no proration is the standard subscription posture encoded in the Terms.
**Reversibility:** locked

## DL-17 — Eligibility: 18+ US-only; parent/guardian managing minor's bills permitted
**Date:** 2026-05-27
**Decided by:** Brock (per legal pack)
**Decision:** Users must be 18+ and US-only; a parent or guardian managing a minor's bills is
permitted.
**Reasoning:** Per the legal pack. Restricting to US adults matches the regulatory posture
and payer/legal coverage; the guardian carve-out covers the common case of a parent handling
a child's medical bills without opening the app to minors directly.
**Reversibility:** locked

## DL-18 — Domain tyndaleapp.net; SendGrid Email API Pro (HIPAA-eligible tier) for sends
**Date:** 2026-05-27
**Decided by:** Phil (CTO) + Brock
**Decision:** Domain is `tyndaleapp.net`; account/notification email runs on SendGrid Email
API Pro — a HIPAA-eligible tier with BAA.
**Reasoning:** Given the consumer-health-data posture, notification email must run on a
HIPAA-eligible tier; SendGrid's standard tier does not include a BAA. Phil and Brock jointly
settled the domain and the email vendor/tier.
**Reversibility:** locked
**Reversed by:** DL-47 + DL-49 — no PHI in emails (runtime invariant) → SendGrid excluded
from the BAA list. The Email API Pro tier choice stands operationally (it's still the tier
we use); the BAA requirement is dropped.

## DL-19 — Counsel engagement + dev team capacity managed outside Cowork
**Date:** 2026-05-27
**Decided by:** Brock
**Decision:** Legal counsel engagement (and legal-pack review) and development-team capacity
are managed by Brock outside Cowork's scope.
**Reasoning:** These are long-lead, people-and-contracts tracks that Cowork doesn't drive.
Recording them here keeps their status visible — counsel blocks Phase 7 publication, and
capacity affects the whole schedule — while ownership stays with Brock.
**Reversibility:** locked

## DL-20 — PostToolUse hook receives DB session via dependency injection

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 1C
**Decision:** The PostToolUse hook signature in `docs/integration-contracts.md` Section 2.1 originally didn't include a DB session parameter. Phil resolved this by having the runtime inject an async SQLAlchemy session via FastAPI's dependency-injection mechanism so the hook can write to `audit_events`.
**Reasoning:** PostToolUse must write to Postgres to log the audit event; without a session, it couldn't. FastAPI's DI is already the runtime's standard pattern.
**Reversibility:** locked unless the security/HIPAA contact has a different preferred approach.

## DL-21 — Feedback table shapes designed by Phil

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 1C
**Decision:** The integration contracts referenced `feedback_events`, `feedback_triage_queue`, and `feedback_deid_candidates` tables but said "shapes defined by Jonas." Phil designed the schemas in `0001_initial.py` per the L05 capture schema, with foreign keys to `case_files` and a status enum (`pending|deidentified|promoted|discarded`).
**Reasoning:** the L06 de-identification pipeline needs a stable handoff schema; pre-defining unblocks Phase 4 work and Phase 2I/J ahead of the security/HIPAA contact engaging.
**Reversibility:** revisable if Jonas or the security/HIPAA contact has different shape requirements.

## DL-22 — Gated-tool argument naming

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 1C
**Decision:** The PreToolUse hook validates `approval_token` for `send_email`/`doc_generate` gated tools and `effective_date` for `qdrant_search_laws_regulations` / `qdrant_search_payer_policies`. Phil committed to these exact arg names so the runtime, tools, and hook all agree.
**Reasoning:** per the build kit, these hooks enforce specific invariants; consistent naming makes the contract enforceable across runtime + tools + hooks.
**Reversibility:** locked.

## DL-23 — Skill scaffolds intentionally shallow

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 2A
**Decision:** The Skill scaffolds (Bill Error Detection, Coverage Connection, etc.) use placeholder `src_TBD` source IDs and representative legal citation language. Real attorney-verified citations and real Qdrant chunk source IDs fill in during Phase 5 + domain-expert engagement.
**Reasoning:** per Tasks 08/10/13, scaffold-then-fill is the intended pattern; building attorney-verified content into Phase 2A would block the build on the attorney's timeline.
**Reversibility:** locked at the scaffold stage; entries fill in as content lands.

## DL-24 — MODES.md not built; v1-lite/universal/full-only conventions remain implicit

**Date:** 2026-05-27
**Decided by:** Brock via Cowork
**Decision:** Tasks L02/L03/L04 reference a MODES.md file tracking which files belong to v1-lite vs universal vs full-only modes. The file is not built. The conventions are encoded implicitly in directory placement, file frontmatter where present, and the deferred-placeholder pattern used consistently across the build.
**Reasoning:** a separate MODES.md is documentation overhead with limited payoff at this team size; the implicit conventions are sufficient.
**Reversibility:** revisable if a future team member finds the implicit conventions ambiguous.

## DL-25 — Marketing landing pivoted from Static Web Apps to external Container Apps environment

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 1E deploy
**Decision:** The Phase 1E spec called for Azure Static Web Apps Free tier for the marketing landing. In practice, SWA + hybrid Next.js + npm-workspace `@tyndale/shared` was incompatible — SWA's Oryx couldn't resolve the workspace dep without bypassing the hybrid runtime, which broke the NextAuth API route. Phil added a second Container Apps Environment (`tyndale-dev-cae-external`) for public-facing apps; the original internal CAE retains runtime/litellm/qdrant.
**Reasoning:** shipping the hybrid Next.js runtime intact preserved the auth API path; the SWA Free-tier cost savings were marginal compared to the engineering effort to work around the hybrid limitation.
**Reversibility:** revisable if SWA later supports hybrid Next.js + workspace deps natively, or if marketing pages collapse to static-export-only.

## DL-26 — GitHub Actions CI/CD with OIDC + GHCR

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 1E deploy
**Decision:** Added `deploy-runtime` and `deploy-web-marketing` GitHub Actions workflows. Both authenticate to Azure via OIDC against the GitHub `dev` environment. Images are hosted on GHCR (public). Auto-deploys on push to `main` when the matching paths change.
**Reasoning:** needed CI/CD to land the real runtime image as soon as Phase 2D wiring completes; GHCR was cheaper and simpler than Azure Container Registry for early dev.
**Reversibility:** ACR migration is a config change if security/HIPAA contact wants registry traffic inside the VPC.

## DL-27 — Custom domain TLS cert binding via az CLI null_resource

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 1E deploy
**Decision:** The `azurerm_container_app_environment_managed_certificate` resource creates a binding/cert dependency cycle when paired with the custom-domain attachment. Phil wrapped `az containerapp hostname bind --validation-method HTTP` in a Terraform `null_resource` that does both halves atomically.
**Reasoning:** pragmatic workaround for an AzureRM provider limitation; cert + binding land together.
**Reversibility:** revisit when AzureRM gains a non-cycling pattern for cert + binding co-creation.

## DL-28 — Opus 4.7 synthetic-generation cost estimate corrected to ~$85

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 2E
**Decision:** The Phase 2E README quoted $10–25 for a full ~2,000-case synthetic generation run. The runner's per-token math against current Anthropic pricing came to ~$85. Updated cost expectation reflected in the synthetic README.
**Reasoning:** original estimate was conservative against the wrong pricing tier; corrected before Brock approves the run.
**Reversibility:** cost falls as pricing tiers shift; update again when Brock confirms enterprise-tier pricing.

## DL-29 — Error-handler middleware logs structured exceptions

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 2D
**Decision:** The `middleware/error_handler.py` was logging only `str(exc)`, which collapsed traceback information and slowed multi-iteration debugging. Replaced with `log.exception` (Python logging) + dev-mode traceback in the response body (production retains the JSON-only error response, no stack to client).
**Reasoning:** structured exception logging cuts debug-loop time significantly on real-Claude integration work where the failure surfaces are varied.
**Reversibility:** locked discipline; applies to all future runtime middleware.

## DL-30 — Env-var validation uses startswith() discipline

**Date:** 2026-05-27
**Decided by:** Phil (CTO) during Phase 2D
**Decision:** Env vars like `ANTHROPIC_API_KEY`, `AZURE_DOC_INTELLIGENCE_ENDPOINT`, and `DATABASE_URL` were being checked via truthiness. Placeholder strings like `<from terraform output>` passed truthiness and crashed the runtime at the first real call. Now use `startswith("https://")` for endpoints, `startswith("sk-")` for API keys, `startswith("postgresql+asyncpg://")` for connection strings.
**Reasoning:** placeholder values are common in dev iteration; failing fast at config-load time beats crashing mid-request.
**Reversibility:** locked across all future config validation.

## DL-31 — Migrations-in-CI Container Apps Job pattern

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H deploy
**Decision:** Database migrations run as a Container Apps Job (`tyndale-dev-runtime-migrations`) on every `deploy-runtime` CI run before the runtime CA rolls. The Job runs `alembic upgrade head` + the dev seed, gates the runtime roll on migration success, uses the same internal CAE (so it reaches VNet-only Postgres), same UAMI + KV-backed `DATABASE_URL`.
**Reasoning:** manual `az containerapp exec` migrations were error-prone and broke CI/CD. Container Apps Jobs are the right Azure primitive for one-shot tasks. Verified CI green end-to-end in 1m35s build → migrate → roll.
**Reversibility:** standard for staging + production; carry forward to those env configs.

## DL-32 — user_type column with admin pre-seeded for Phase 2K auth swap

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H
**Decision:** Alembic migration 0002 adds `users.user_type` (CHECK IN ('user', 'admin'), default 'user'). The dev seed creates `pfluegelcx@gmail.com` as `user_type='admin'`.
**Reasoning:** Phase 2K's Google sign-in flow matches users on verified email; the admin user already exists with the right role, so the auth swap requires zero additional data migration.
**Reversibility:** revisable; matches industry-standard user/admin role distinction.

## DL-33 — DATABASE_URL urlencodes special characters in Postgres password

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H
**Decision:** SQLAlchemy + asyncpg fails to parse `DATABASE_URL` when the Postgres password contains `@` or `:` or other URL-reserved characters. Passwords are now URL-encoded before being assembled into `DATABASE_URL` in Terraform locals.
**Reasoning:** Azure Postgres password generation can include special characters; the URL parser misreads them as delimiters.
**Reversibility:** locked across all envs.

## DL-34 — Azure Key Vault references use versionless_id for Container App secrets

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H
**Decision:** When binding Key Vault secrets to Container App secret references via Terraform, use `azurerm_key_vault_secret.<x>.versionless_id`, not `.id`. Version-pinned secret IDs trip an AzureRM provider inconsistent-plan bug.
**Reasoning:** KV secrets rotate; references should follow the current version automatically, not pin to a specific version that won't exist after rotation.
**Reversibility:** locked.

## DL-35 — Postgres Flexible Server requires extensions allow-listed via azure.extensions

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H
**Decision:** `CREATE EXTENSION pgcrypto` in Alembic migration 0001 fails on Azure Postgres Flexible Server unless 'pgcrypto' is listed in the `azure.extensions` server parameter. Terraform now sets the `azurerm_postgresql_flexible_server_configuration "azure.extensions"` value to include `pgcrypto` (plus any other extensions used).
**Reasoning:** Azure Postgres Flex requires explicit allow-listing for security; this is by design but not obvious from the error message.
**Reversibility:** locked; add new extensions to the configuration as they're needed.

## DL-36 — Alembic down_revision matches actual revision IDs

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H
**Decision:** Alembic `0002.down_revision` originally referenced `"0001_initial"` (the filename prefix) but the actual revision ID is `"0001"`. Migrations now use the bare ID, not the filename prefix.
**Reasoning:** Alembic's down_revision is a revision ID, not a filename; the linter doesn't catch the mismatch but Alembic fails at runtime.
**Reversibility:** locked discipline.

## DL-37 — CI az polling uses explicit status flags

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2H
**Decision:** The CI workflow's status-poll for the migration Job was using wrong `az` flags and printed a fake "Pending" 60×, masking the real outcome. Now uses `az containerapp job execution show --query 'properties.status' -o tsv` with explicit timeout and exit-on-Succeeded/Failed.
**Reasoning:** silent status-poll failures cascade into hours of confused debugging; explicit polling with clean exits surfaces real failures fast.
**Reversibility:** locked CI discipline.

## DL-38 — packages/shared barrel-export discipline + mobile typecheck in CI gap

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2I
**Decision:** `packages/shared/src/index.ts` barrel export must include every type module; missing exports don't surface as build errors when mobile isn't typechecked in CI (Phase 2H's dashboard export was lost; Phase 2I's encounter export was caught only because Phil ran the typecheck locally). Two-part discipline: (a) every new file under `packages/shared/src/` requires a corresponding `export * from './<module>'` in `src/index.ts`; (b) GitHub Actions runs `tsc --noEmit -p apps/mobile` + `apps/web-marketing` on every PR.
**Reasoning:** silent barrel-export regressions cascade as runtime ImportErrors and consumed multiple iterations to debug. Mobile typecheck job in CI catches these on PR.
**Reversibility:** locked. Mobile typecheck CI job lands in Phase 2K.

## DL-39 — Structured persistence uses dedicated tools, not free-text parsing

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2I
**Decision:** When a subagent needs to persist structured data (line items, findings, deadlines, plan state), it calls a dedicated typed tool like `pg_store_line_item` or `pg_upsert_finding` rather than producing free text the runtime parses. Phase 2I added `pg_store_line_item`; the same pattern applies to any future structured persistence.
**Reasoning:** the tool registry pattern is already the contract between agent and runtime; using it for persistence keeps the boundary clean, validates argument shapes at call time, and gives the PreToolUse hook a natural place to scrub PHI before storage.
**Reversibility:** locked.

## DL-40 — pytest-asyncio + asyncpg event-loop fixture pattern

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2I
**Decision:** Tests that share an async DB engine across many test cases require an autouse fixture in `conftest.py` that disposes the app engine after each test. pytest-asyncio's per-test event loops collide with asyncpg's default connection pool, producing `RuntimeError: Event loop is closed` on the second test. The autouse dispose is test-only and adds no production overhead.
**Reasoning:** pytest-asyncio + asyncpg compatibility quirk; documented so future test authors don't re-debug it.
**Reversibility:** revisit if pytest-asyncio + asyncpg add native compatibility.

## DL-41 — GET /v1/audit/{id} returns assembled result, not 404-until-finalized

**Date:** 2026-05-28
**Decided by:** Phil (CTO) during Phase 2I
**Decision:** The audit GET endpoint returns the current assembled result (which may be partial during the two-phase flow) rather than 404'ing until the audit is fully complete. Frontend gates rendering on `/audit/{id}/status == 'audit_complete'` before calling.
**Reasoning:** keeps the legacy POST `/v1/audit` single-phase path working unchanged; avoids two different error semantics on the same URL.
**Reversibility:** revisable if the API surface gets larger and explicit lifecycle endpoints make more sense.

## DL-42 — Runtime is a public API at api.tyndaleapp.net (no longer internal-only)

**Date:** 2026-05-29
**Decided by:** Phil (CTO) during the Phase 2K auth rollout
**Decision:** The runtime Container App moved from the internal-only CAE (`tyndale-dev-cae`) to the external CAE (`tyndale-dev-cae-external`) with public ingress, fronted by `api.tyndaleapp.net` (Azure-managed TLS). Real auth (`use_real_auth=true`) requires the browser/mobile app to reach `/v1/auth/*` and receive a session cookie scoped to `.tyndaleapp.net`; an internal CAE exposes no public endpoint, and a raw `*.azurecontainerapps.io` host cannot set a `.tyndaleapp.net` cookie — so the runtime had to be public on a `tyndaleapp.net` subdomain. CORS allows the `dev.`/`app.` web origins with credentials. The internal CAE still hosts qdrant, litellm, and the migrations job; the runtime reaches those + the VNet-only Postgres over the shared `tyndale-dev-vnet`. The domain + managed cert are gated/phased via `enable_runtime_custom_domain` + `enable_runtime_managed_cert` (mirrors the marketing domain). `NEXT_PUBLIC_RUNTIME_URL` is baked into the marketing build as a Docker build-arg (NEXT_PUBLIC_* is inlined by `next build`), not a Container App env var.
**Reasoning:** the mobile product fundamentally needs a public HTTPS API (a native app can't use a same-origin web proxy), so a public authed API on a dedicated subdomain is the honest topology. A Next.js reverse-proxy (keeping the runtime internal) was considered but only serves the web surface. The runtime is an authed API; network hardening (rate limits / IP restrictions / WAF) is deferred to a later phase.
**Reversibility:** reversible — move the runtime back to the internal CAE and front it with a reverse proxy or Application Gateway if a stricter network posture is later required; the `api.tyndaleapp.net` contract stays stable across either.

## DL-43 — Product app (apps/mobile) deployed to app.tyndaleapp.net as a static web export

**Date:** 2026-05-29
**Decided by:** Phil (CTO)
**Decision:** The signed-in product UI (the Expo/React-Native-Web app in `apps/mobile`) is deployed to **`app.tyndaleapp.net`** as a **static web export** (`expo export --platform web`, `web.output: 'static'`) served by a small **nginx Container App** in the external CAE — mirroring the marketing/runtime pattern (DNS CNAME + asuid TXT + custom domain + managed TLS cert, gated by `enable_app_custom_domain` / `enable_app_managed_cert`; deploy-app.yml builds → GHCR → rolls the CA). `EXPO_PUBLIC_API_BASE_URL=https://api.tyndaleapp.net` is baked at build time (build-arg). Marketing stays at `dev.tyndaleapp.net`; the `.tyndaleapp.net` session cookie is shared across `dev.`/`app.`/`api.` so a user signed in via the marketing flow carries straight into the app.
**Reasoning:** the dashboard/upload/cases screens live only in the Expo app, not the marketing Next.js app; a native app also can't use a same-origin web proxy, so a dedicated public surface is needed. Static export + nginx keeps it a cheap, stateless CA consistent with the rest of the stack. Azure Static Web Apps was considered but a Container App keeps one deploy model + reuses the proven DNS/cert flow.
**Reversibility:** revisable — could move to SWA or serve the app under a `dev.tyndaleapp.net/app` path later; the `app.tyndaleapp.net` contract is stable.

## DL-44 — React is deduped at the Metro bundler, not in the npm tree

**Date:** 2026-05-30
**Decided by:** Phil (CTO)
**Decision:** The Expo web app must bundle exactly one React. `apps/mobile` pins `react 19.0.0` (Expo SDK 53) while `apps/web-marketing`'s transitive deps float React to 19.2.x, which npm hoists to the workspace root — leaving **two physical React copies**, which Metro bundled into the web app → two React instances → null hook dispatcher → `TypeError: Cannot read properties of null (reading 'useState')` → white screen on first render. The fix is a `metro.config.js` `resolveRequest` that forces every `react`/`react-dom` import (incl. subpaths like `react/jsx-runtime`) to resolve from the workspace root. **Do NOT try to dedupe via npm** (`overrides` / clean reinstall): a pre-existing peer conflict — `react-native-worklets@0.9.1` peers `react-native 0.83–0.86` vs our `0.79.6` — makes any clean `npm install` **ERESOLVE**, so the committed lockfile must be installed via `npm ci` and not regenerated.
**Reasoning:** the bundler-level alias is the documented Expo-monorepo approach, touches no dependencies, and sidesteps the worklets ERESOLVE. Verified: the export bundle then carries a single React version string.
**Reversibility:** revisit if the workspace later collapses to a single declared React version (then the resolver can be removed) or if the worklets/RN peer conflict is resolved.

## DL-45 — App→API calls send credentials; SPA HTML is served no-cache

**Date:** 2026-05-30
**Decided by:** Phil (CTO)
**Decision:** Two cross-cutting web rules. (1) **Every** runtime API call from the app/marketing clients must use `credentials: 'include'` — `app.` and `api.` are different `.tyndaleapp.net` subdomains (cross-origin), so without it the session cookie isn't sent and the runtime returns `401 "not authenticated"`. In `apps/mobile/lib/api-client.ts` all calls route through a single `cfetch()` wrapper that sets it. (2) The static-web nginx serves **`Cache-Control: no-cache` on HTML** (`index.html` / route `.html`) while keeping the hashed `/_expo` + `/assets` chunks immutable — otherwise browsers keep a stale `index.html` that points at deleted chunk hashes after a deploy, requiring a manual hard-refresh.
**Reasoning:** the 401 was silent (only the auth calls had credentials; the data calls didn't), and the stale-HTML caching made every deploy look broken until a hard-refresh. Both are easy to reintroduce, hence logged.
**Reversibility:** stable rules; revisit only if auth moves to bearer tokens (then credentials/cookies may not apply) or the app stops being a static SPA.

## DL-46 — Runtime hardening (Phase 2K.2) for public api.tyndaleapp.net

**Date:** 2026-05-30
**Decided by:** Phil (CTO) during Phase 2K.2
**Decision:** Runtime hardened to fill the post-DL-42 public-ingress gap. Rate limiting expanded to all routes (per-IP baseline, per-user when authenticated, per-route caps on expensive ops). Security headers middleware (HSTS, X-Frame-Options, etc.). Request size limits (25 MB total / 20 MB per file / 1 MB JSON). Error response hardening (no traceback in prod; correlation_id + request_id for log lookup). JWT validation made explicit (algorithm allow-list, audience, issuer, required claims). CORS explicit allow-list (never wildcard). Session cookie uses the `__Secure-` prefix over HTTPS with a 30-day legacy-name read grace. Basic PHI-pattern log filter as a bridge before Presidio. IP-allowlist middleware ready for admin paths. Two deliberate deviations preserve the live deployment: (1) JWT `aud`/`iss` VALUES kept as `session`/`tyndale` (not renamed) so existing sessions aren't invalidated — the explicit-validation security property is what matters and is satisfied; (2) the `__Secure-` prefix is applied only when `cookie_secure` so local http dev/tests aren't broken.
**Reasoning:** developer-spec D9 assumed internal-only ingress; DL-42 made the runtime public; the gap had to be filled before exposing real user traffic. Phase 4 (security/HIPAA contact) takes over Presidio, encrypted audit log, Redis rate limiter, and WAF. See `docs/runtime-hardening.md`.
**Reversibility:** locked at the application layer; Phase 4 infrastructure work (WAF, Redis) replaces specific pieces over time.

## DL-47 — No PHI in emails, ever (runtime invariant)

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Email must stay free of protected health information as the product grows. Magic-link sign-in, account notifications, and generic "your report is ready" messages are permitted. Anything referencing a bill, a diagnosis, a care-related dollar amount, case details, or any health information is NOT permitted. Encoded as a runtime invariant: a PreToolUse hook on the `send_email` tool scans content for PHI patterns and rejects before send. Not convention.
**Reasoning:** firm architectural rule — also justifies SendGrid's exclusion from the BAA list (only safe to exclude *because* email is guaranteed PHI-free).
**Reversibility:** locked. If ever changed, a SendGrid BAA becomes required.

## DL-48 — Apple Developer enrollment: NO; web-only for V1-Lite

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Web app only to start. Native iOS app and Apple Developer enrollment are deferred indefinitely. Phase 3 (mobile polish + native iOS submission prep + Apple Sign-In) dropped from the Cowork queue. `app.tyndaleapp.net` is the V1-Lite product surface.
**Reasoning:** reduces scope and avoids App Store Guideline 4.8's Apple Sign-In dependency until native mobile becomes a real product priority.
**Reversibility:** revisable if native mobile becomes a Full V1+ priority.

## DL-49 — BAA list of 5 (Anthropic, Azure, AWS, Voyage AI, 1upHealth)

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Five V1-launch-critical BAAs: Anthropic (HIPAA-eligible enterprise tier), Azure, AWS, Voyage AI, 1upHealth. **Stripe permanently excluded** — payment processing walled off; anonymized IDs (UUIDs) only, never bill details / diagnoses / health information. **SendGrid excluded** because email is guaranteed PHI-free per DL-47. **Observability vendor BAA conditional** on Phase 4 PHI scrubbing proving PHI can't reach logs — verify "PHI-free logs" before signing or skipping.
**Reasoning:** scoped BAA chain to what actually receives PHI; walls off Stripe entirely; uses the no-PHI-in-emails rule to avoid an unnecessary SendGrid BAA.
**Reversibility:** Stripe and SendGrid exclusions are locked unless the architectural rules that justify them change.

## DL-50 — Trilliant replaces FAIR Health; hands-off pattern

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Trilliant is the chosen vendor for procedure-level price-estimate data, replacing FAIR Health in all prior planning. Contract pending. **Cowork does not ping Brock on Trilliant** — Brock surfaces when contract is live. Until live, cost estimation runs on Medicare PFS + Hospital MRF + TiC; Trilliant slots in behind the pricing interface when available.
**Reasoning:** clean vendor swap; Brock owns the commercial conversation without Cowork chase-up overhead.
**Reversibility:** revisable if Trilliant doesn't materialize and an alternative vendor is needed.

## DL-51 — MCG and InterQual never scraped

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** MCG and InterQual proprietary medical-necessity criteria are paywalled. Do NOT scrape or republish. Capture only payers' own published policies and PA lists for the payer-policy ingestion pipeline.
**Reasoning:** copyright + license violation risk if scraped; not worth the exposure.
**Reversibility:** locked unless a licensed access path becomes available.

## DL-52 — No Stedi / no real-time eligibility

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Stedi and any real-time eligibility (270/271) integration are removed from V1-Lite + CO-002 scope. No eligibility vendor, no payer enrollment, no NPI-gating logic. The user's benefits, deductible, and out-of-pocket status come entirely from the guided capture in CO-002 Item 1.
**Reasoning:** D2C app has no billing-provider NPI of its own; per-payer Stedi enrollment friction is high; guided capture covers the data need without the eligibility-vendor overhead.
**Reversibility:** revisable far down the road if real-time eligibility becomes meaningfully valuable.
**Conditionally superseded by:** DL-70 — the eligibility/NPI seam is built as gated-closed config (CO-12A), but DL-52's removal of the *adapter* holds until DL-70's three conditions (signed BAA, resolved NPI posture, formal DL-52 supersession) all clear.

## DL-53 — TiC MRFs ingested in initial cost-data pipeline

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Insurer Transparency-in-Coverage MRFs are part of the initial cost-estimation pipeline, not deferred. Aggressive ghost-rate filtering required (~84–92% of TiC rows are ghost rates and must be filtered before any TiC data informs a user-facing estimate). Reversed from CO-002 v1's "trigger later."
**Reasoning:** broadens cost coverage to ambulatory/outpatient/clinic settings that hospital MRFs miss; worth the ingestion + filtering investment up-front.
**Reversibility:** locked into the initial pipeline.

## DL-54 — CPT placeholders across all features until license clears

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Until the CPT licensing path resolves (Brock confirming whether Trilliant's AMA license covers Tyndale's display, or falling back to AMA Information Provider tier), all user-facing surfaces showing procedure descriptions use placeholder descriptors ("MRI of the head") rather than the official CPT descriptor + code number. Internal storage of codes (which are facts on bills) is fine; display to users is gated. Swap in real descriptors once the AMA path lands. Do not block other feature work on CPT licensing.
**Reasoning:** unblocks Items 1–4 from CPT-licensing timing; only Item 5 (appeals) stays OFF until CPT data is live (per DL-55).
**Reversibility:** automatic on CPT license clearing.

## DL-55 — Appeals built in shadow mode + feature OFF until CPT data live

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Appeals / network-deficiency document generation is built in shadow mode now (generates silently, routes to admin console for Brock's review), but the feature flag is **OFF** — no generation against real CPT data, nothing shown to users — until Trilliant or AMA CPT data is up and running.
**Reasoning:** appeals is the highest-liability output; AI hallucination of policy/medical claims is the central risk; shadow mode + feature-off-until-CPT-data + Brock manual review (per DL-56) layered mitigation.
**Reversibility:** Brock flips ON per document type when ready (DL-56).

## DL-56 — Appeals promotion = Brock's manual per-document-type call

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Promotion of an appeal / network-deficiency document type from shadow mode to user-facing is Brock's manual call, per document type. No metric-threshold auto-promotion. The admin console surfaces review volume + correctness + ungrounded-claim flags to *inform* Brock's decision, but the flip is his explicit call.
**Reasoning:** preserves human judgment on a high-liability surface; per-type promotion (internal appeal first, external review next, DOI complaint after, etc.) lets each document type clear its own bar.
**Reversibility:** locked — auto-promotion is not on the table.

## DL-57 — V1-Lite launch path protected; CO-002 parallel; resourcing handled

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** CO-002 features build in parallel with the V1-Lite launch path. The launch path is protected — CO-002 work must not delay launch gates (security/HIPAA contact engagement, CPT licensing path, 5 BAAs). Resourcing is handled (Phil + Brock's developers + Claude Code + Cowork autonomous); do not re-raise dev capacity as a blocker.
**Reasoning:** clear separation between launch-critical work and feature-expansion work; explicit guardrail against feature work starving launch attention.
**Reversibility:** locked for the V1-Lite launch window.

## DL-58 — Continuous expansion mandate (hospitals past 100, payers past 7, TiC past Tier-1)

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** Starting sets are not ceilings. Hospital MRF ingestion starts with top 100 hospitals by volume and continues expanding in waves. Payer-policy scraping starts with the core 7 (Aetna CPBs, Cigna, UHC, Anthem/Elevance, Humana, Centene/Wellcare, Molina) and continues expanding to additional payers. TiC ingestion starts with the same Tier-1 commercial payers and continues expanding. Treat all three as continuously expanding coverage over time.
**Reasoning:** establishes that breadth-of-coverage work is ongoing, not one-off; gives Cowork explicit authority to keep expanding without re-asking.
**Reversibility:** expansion pace can be tuned but the mandate itself is locked.

## DL-59 — ≥90% structural extraction confidence quality bar for new payer/source promotion

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** A newly-scraped payer / newly-ingested data source must pass ≥90% structural extraction confidence on a 20-policy (or equivalent sample) before entering live retrieval. New sources land in a `staging` partition first; promotion to `live` happens after the sample passes. Failed sources are flagged for review / extraction-prompt tuning before re-attempt. Applies to the DL-58 continuous expansion mandate.
**Reasoning:** safeguards retrieval quality of the core sources from contamination by long-tail expansion failures.
**Reversibility:** the 90% threshold is the starting point; tunable as the pipeline matures.

## DL-60 — Admin console at admin.tyndaleapp.net subdomain + dual-layer auth

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** The admin console lives on a separate `admin.tyndaleapp.net` subdomain (not `app.tyndaleapp.net/admin/*`). Dual-layer authentication: (a) application-layer `current_user.user_type == 'admin'` check on every admin route, (b) network-layer Container Apps ingress IP allowlist via Application Gateway. Non-admin attempts to access return 404 (anti-enumeration). Brock-only at launch; security/HIPAA contact gets scoped admin access when they engage. Brock provides the allowed-IP list when admin console work starts.
**Reasoning:** separate subdomain is cleaner + safer + isolates admin failure modes from the user product; dual-layer auth + 404-not-403 follows the Phase 2K.2 hardening posture.
**Reversibility:** locked.

## DL-61 — Public-examples corpus compiled by Cowork; per-example source/license tagging required; "fair use" NOT settled

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** The corpus of public example documents that Tyndale's appeals/network-deficiency generation draws from is compiled by Cowork from public sources (state Department of Insurance complaint archives, PatientAdvocate.org, Kaiser Family Foundation samples, AAEM-PG templates, state AG health-care complaint examples). Each example is stored with frontmatter capturing: `source_url`, `source_organization`, `license`, `document_type`, `state`, `date_added`. Per-example source/license tagging is REQUIRED, not optional. Treat examples as internal reference material to shape how Tyndale writes its own documents — **NOT as a settled legal determination that "fair use" applies.** Revisit with counsel before appeals ever becomes a fully user-facing feature.
**Reasoning:** unblocks appeals development without counsel engagement, but preserves the option to remove/replace anything problematic later by keeping full source/license metadata; honest about the legal posture (deferred, not eliminated).
**Reversibility:** corpus contents are removable on counsel's later review; the per-example tagging discipline is locked.

## DL-62 — Eval-generation cost at standard Anthropic pricing (~$85)

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** The synthetic eval generation run (~2,250 cases per Phase 2E's design) proceeds at standard Anthropic pricing (~$85 one-time). Do not chase enterprise pricing for this specifically; if Brock is already in an Anthropic BAA/enterprise-tier conversation, the pricing question can be raised there, otherwise ignore.
**Reasoning:** cost is small enough to not warrant a separate procurement effort; enterprise pricing is a bigger conversation.
**Reversibility:** revisable once enterprise pricing is known.

## DL-63 — TiC ghost-rate filtering as tunable starting posture

**Date:** 2026-05-30
**Decided by:** Brock via CO-002 FINAL
**Decision:** TiC MRF rows are filtered using these starting heuristics: rate ≠ 0; rate within 30%–500% of Medicare allowable for the same code+region; rate present in ≥2 distinct payer files (single-occurrence rates flagged as likely-ghost). Surviving rows enter the `transparency_rates` table weighted by a `confidence_score` (number of corroborating sources, distance from Medicare median, recency). Specific thresholds are a starting point to tune once real estimates can be compared against real bills — not a permanent setting.
**Reasoning:** explicit starting posture so the pipeline can ingest now; explicit "tunable" framing so iteration is expected.
**Reversibility:** thresholds tuned as production data accumulates.

## DL-64 — PHI/security regex discipline: broaden over narrow

**Date:** 2026-05-30
**Decided by:** Phil (CTO) during Phase CO-8
**Decision:** When writing detection regexes for PHI or other security-critical content (in PreToolUse hooks, log filters, validation middleware), default to the broader pattern. The spec for CO-8 specified a CPT regex `\b(?:9[0-9]{4}|0[0-9]{4})\b` (covering only 90000–99999 and 00000–09999) which would have missed CPT 27447 from the same prompt's own test. The implementation uses `\b\d{5}\b` (any 5-digit numeric) instead. Same discipline applied to MRN/ACCT/CLAIM patterns (case-insensitive variants).
**Reasoning:** for guardrails where the cost asymmetry is "false positive forces using a template = mild friction; false negative leaks PHI = breach," the broader regex is the safe default. Spec'd narrow regexes get corrected at implementation time.
**Reversibility:** locked discipline for any security/PHI detection pattern.

## DL-65 — Hook pattern: sync evaluate + async guard split for audit writes

**Date:** 2026-05-30
**Decided by:** Phil (CTO) during Phase CO-8
**Decision:** PreToolUse hooks that need to write audit events split into two functions: (a) a pure synchronous `evaluate_*()` returning the decision (approved=True/False + block_reason), and (b) an async `guard_*(input, session)` wrapping the evaluator with audit-log persistence. The sync hook calls the evaluator for the decision (so blocks hold even without a session); the async runtime path calls the guard for full audit. Tests target the evaluator directly; the async path's audit write is covered by a separate audit test.
**Reasoning:** the Claude Agent SDK's PreToolUse hooks are synchronous + session-less by design; audit writes require an async SQLAlchemy session. Pretending the hook could do both directly (as the CO-8 prompt's pseudocode did) would break at runtime. The split is the architecturally honest pattern; future PreToolUse hooks adopt the same shape.
**Reversibility:** locked pattern across all future PreToolUse hook implementations.

## DL-66 — Migration discipline: backfill existing rows when adding required-status columns

**Date:** 2026-05-30
**Decided by:** Phil (CTO) during Phase CO-1A
**Decision:** When an Alembic migration adds a NOT NULL column representing a workflow status that defaults to "not started" (e.g., `intake_status DEFAULT 'not_started'`), the migration MUST also backfill existing rows to the appropriate "already complete" value where the workflow concept didn't exist before the migration. CO-1A's migration 0009 backfills existing case files to `intake_status='complete'` rather than re-onboarding every existing user into the new wizard. Same pattern applies to any future status-column addition.
**Reasoning:** literal `DEFAULT 'not_started'` is correct for new rows but hostile to existing users who completed their version of the workflow before the column existed. Backfill is the user-respecting default.
**Reversibility:** locked discipline; check on every status-adding migration.

## DL-67 — Medicare Conversion Factor requires annual operational bump

**Date:** 2026-05-31
**Decided by:** Phil (CTO) during Phase CO-3A
**Decision:** The Medicare PFS adapter hardcodes the conversion factor (CF) as a default — currently 32.3465 for 2026. CMS publishes a new CF each year (typically in the Final Rule each November/December for the following year). The Medicare PFS ingestion path must be updated annually with the new CF. Operationally: (a) the constant `MEDICARE_CF_2026 = 32.3465` is replaced by `MEDICARE_CF_<year>` each January; (b) the `medicare_pfs_cron` logs a warning if `effective_year != current_year`, which surfaces as an admin-console alert; (c) a recurring annual calendar reminder for "Update Medicare CF" is part of the operational checklist.
**Reasoning:** the CF directly drives Medicare allowable-amount calculations and the ghost-rate filter's anchor (DL-63). Using last year's CF in this year's estimates produces silent ~2-4% errors that compound across thousands of estimates. Better to fail loud than degrade silently — the warning forces the operational update.
**Reversibility:** locked annual discipline; tied to CMS's publication cadence.

## DL-68 — Four data interfaces as the canonical wrapper-readiness seam

**Date:** 2026-06-20
**Decided by:** Brock (founder), approving Phil's 2026-06-19 Version A / wrapper-readiness response
**Decision:** Patient-specific data is read through four named interfaces — **CoverageSource** (benefit design), **AccumulatorSource** (amount spent toward deductible/OOP, as-of a date), **ClinicalEncounterSource** (visit date / reason / what was done), and **ClaimsSource** (billed-to-payer line data). Agents call these interfaces, never a parser or vendor directly. Each interface may have multiple adapters; the adapter layer decides precedence and cross-validates when more than one answers. CoverageSource + AccumulatorSource are paired behind a single `BenefitsContext` facade (they are read together, a vendor answers both in one call, and the three-way cross-validation lives in one place). The pattern is modeled on the already-shipped `knowledge/cost_estimation.py` multi-source aggregator and the existing `upload_extract_coverage` ≡ `fhir_get_coverage` return-shape convention — this formalizes a proven pattern, not new architecture. Wrapper (Jonas) registers `OneUpHealth*` / eligibility adapters later behind the same interfaces with zero agent change.
**Reasoning:** the seam lets Version A (uploads + public data + computed) and the future vendor sources coexist behind one stable contract, so the agents never get rewritten when 1upHealth / an eligibility vendor lands. Conceptual risk is low because the code already does this for pricing.
**Reversibility:** the four-interface cut is locked; the `BenefitsContext` grouping and per-interface adapter set evolve as adapters are added.

## DL-69 — Typed `Provenance` object supersedes the bare `extraction_source` string

**Date:** 2026-06-20
**Decided by:** Brock (founder), approving Phil's 2026-06-19 response
**Decision:** Every interface return (DL-68) carries a typed `Provenance` object — `adapter`, `source_kind` (`user_upload` | `public_data` | `computed` | `vendor`), `as_of`, `confidence`, `assumptions[]` — replacing the bare `extraction_source: "upload"` string currently emitted by the upload-extract tools. `as_of` is **mandatory** for AccumulatorSource (accumulator math is freshness-sensitive; the patient-data interfaces carry no as-of today). `Provenance` is a strict superset of what is persisted now, so the change is additive; it is threaded into the case file and findings. Shared model lives in `packages/shared` with a runtime mirror.
**Reasoning:** makes every interface honest about where / when / how-sure the data is, which the Independent Audit and Grounding doctrines require; the missing `as_of` is the field the reconstruction engine is most sensitive to.
**Reversibility:** locked shape; fields may be added, not removed.

## DL-70 — Eligibility/NPI seam built as gated-closed config; adapter withheld pending three conditions

**Date:** 2026-06-20
**Decided by:** Brock (founder), approving Phil's 2026-06-19 response
**Decision:** The eligibility seam (the AccumulatorSource + CoverageSource pair, where a Stedi/pVerify adapter would register, NPI-gated) is built **as config only** — an NPI-gating flag defaulted **closed**. No Stedi/pVerify adapter is implemented or enabled until **all three** conditions clear: (1) DL-52 is formally superseded, (2) the NPI posture is resolved (whether Tyndale obtains its own billing-provider NPI — the original DL-52 blocker), (3) a signed BAA covering the eligibility vendor is in place (the vendor is **not** in the DL-49 BAA-5, and the eligibility path needs PHI to function, so it cannot ride a non-BAA path). Brock owns the BAA + NPI-posture track on the founder side, running in parallel; it does not block CO-12A–D. The adapter stays gated-closed regardless of how fast that track moves. Conditionally supersedes DL-52 (forward-pointer added there).
**Reasoning:** building the gate is cheap and reversible and keeps the seam ready; building the adapter now would be wasted work and a compliance reversal (DL-52 + non-BAA vendor).
**Reversibility:** the gate is permanent config; the adapter unlocks only when the three conditions are jointly met.

## DL-71 — Claude-for-Healthcare connector adopt/keep/re-point decisions

**Date:** 2026-06-20
**Decided by:** Brock (founder), approving Phil's 2026-06-19 response
**Decision:** **Adopt** the FHIR-development Agent Skill (authoring acceleration for Jonas's wrapper; no runtime lock-in), the managed **ICD-10 connector** (no ICD-10 catalog exists today — only a code-extraction regex over NCD/LCD text), and the managed **NPI connector for lookup only**. **Keep self-built:** CMS NCD/LCD coverage ingestion (already shipped CO-2A, with staging/live promotion DL-59, effective-date filtering, ghost-rate discipline DL-63) and the sanctions join (OIG LEIE + SAM.gov + state boards + network status) — the NPI connector won't do that join; final NPI-vs-sanctions architecture is decided at find-a-doc build time. **Re-point:** the Prior-authorization-review Skill (built for the payer side) as a scaffold for appeals/visit-planning logic inverted to patient advocacy; its determination-for-payer stance is explicitly rejected. The three data connectors carry PHI-free public reference data, so the BAA constraint doesn't bind them — the decision is build-vs-maintenance economics only.
**Reasoning:** adopt where a managed connector saves net engineering on data we'd otherwise build from scratch (ICD-10, NPI lookup); keep what is already shipped and load-bearing for the Independent Audit (CMS coverage) or that a connector can't replicate (sanctions join).
**Reversibility:** per-connector calls are revisable; each swap that lands gets its own follow-on note.

## DL-72 — Accumulator reconstruction is a pure deterministic engine with three-way cross-validation

**Date:** 2026-06-23
**Decided by:** Phil (CTO) during Phase CO-12B
**Decision:** The AccumulatorSource (deductible/OOP met, as-of a date) is reconstructed by a **pure deterministic engine** (`ComputedFromUploadedEOBs`) that sums the applied-amounts across the uploaded EOBs — **never** a model/LLM computation. It is paired with `EOBStatedYTD` (the EOB's own stated year-to-date figures, read but **never adopted**). `BenefitsContext.get_accumulator` performs a **three-way cross-validation** of the computed reconstruction against (a) the EOB-stated YTD and (b) the user/card-stated `coverage.deductible_met` / `oop_max_met`; a material disagreement (> $1 **and** > 5%) emits exactly one `accumulator_discrepancy` Finding (`finding_type=payer_side`, `voice_tier=A`, `subagent_source=math_person`) carrying all three readings — the computed figure stays authoritative (Independent Audit Doctrine). The engine **degrades gracefully** rather than dead-ending: undated EOBs are included + flagged, missing family/embedded plan structure falls back to a single individual/in-network bucket with a recorded assumption, and a **completeness gate** ("all of this plan year's EOBs uploaded", read from the call args or a persisted `coverage._all_eobs_uploaded` flag) lowers `confidence` + records the assumption when unconfirmed. The registry resolver stays single-adapter passthrough (YAGNI per DL-68); the cross-validation is a bespoke step in `BenefitsContext`, not a generic n>1 merge engine.
**Reasoning:** the accumulator is the load-bearing input to the Independent Audit's third number, so it must be computed independently of the payer's claim and reconciled against it — disagreement is a finding, not an error to smooth over. Determinism keeps the math auditable and reproducible; graceful degradation keeps it useful on the incomplete EOB sets real users have.
**Reversibility:** the tolerance thresholds and the confidence formula are tunable; the deterministic + cross-validate + finding-on-disagreement discipline is locked.

## DL-73 — PlanLibrary: plan-level designs only (no PHI); no silent prior-year carry-forward; confirm-increments / reject-forks

**Date:** 2026-06-23
**Decided by:** Phil (CTO) during Phase CO-12C
**Decision:** The PlanLibrary stores **plan-level benefit designs ONLY** — keyed by (payer, plan id/name, plan year), holding deductible / coinsurance / OOP / copay terms. Every user identifier (member id, name, group-as-identifier, subscriber, DOB, account/claim numbers, address, free-text) **and** every per-person amount (deductible/OOP *met*) is stripped before write via an **allowlist** (`strip_identifiers` keeps known benefit keys and drops everything else, so even unanticipated keys can't leak): the library never holds PHI. A stored design is **never applied to a current-year claim from a prior plan year without explicit confirmation** — a plan-year mismatch is not a match. A user **confirm** increments the stored design's `confidence`; a **reject forks** a new entry (PHI-stripped corrected design) rather than overwriting, and archives the prior pointer into `plan_history`. All confirmed coverage still lands in `CaseFile.coverage` (the canonical store) — PlanLibrary only **proposes**; it is a secondary CoverageSource adapter (below UserUploadedSBC) and `registry.resolve()` is unchanged.
**Reasoning:** the PlanLibrary is the graceful-degradation rescue for the healthcare-naive user who can't find or name their benefits doc — "Looks like you're on {plan}; does this match?" beats dead-ending on "upload your SBC." Storing only plan-level designs keeps it PHI-free (shareable across users); confirm/fork keeps it honest as real designs vary.
**Reversibility:** matching heuristics + the confidence model are tunable; the PHI-strip (plan-level only), no-silent-carry-forward, and confirm/fork discipline are locked.

## DL-74 — laws_regulations uses Voyage's contextualized-embeddings endpoint (voyage-context-3)

**Date:** 2026-06-23
**Decided by:** Phil (CTO) during Phase CO-13
**Decision:** The `laws_regulations` collection embeds via Voyage's **contextualized**-embeddings endpoint (`/v1/contextualizedembeddings`, `voyage-context-3`), not the flat `/v1/embeddings` path. Stored chunks are embedded `input_type="document"` **grouped by parent authority** (statute + parent_part) so each chunk is embedded aware of its neighbors; queries are embedded `input_type="query"`. The query and the stored chunks **must use the same model + matching input_type** or retrieval silently degrades. Switching a collection's embedding model/endpoint **requires re-seeding** the collection — vectors from different endpoints (or from the no-key stub) are not cross-comparable. The flat `voyage-3-large` path (billing_codes, error_detection_rules, payer_policies) and the no-key deterministic stub are unchanged; the collection config (1024-dim cosine) is unchanged, so no Qdrant re-creation / DB migration.
**Reasoning:** `laws_regulations` backs Tier-B legal/coverage claims; legal text is chunked from long parent authorities, and contextualized embeddings materially improve "find the right subsection" retrieval — the spec locked `voyage-context-3` for it precisely for this. Until the contextualized endpoint was wired, the strongest grounding collection was the weakest in practice (it only "worked" via the stub).
**Reversibility:** the model choice is revisable, but the re-seed-on-switch requirement is locked (vectors aren't comparable across endpoints/models).

## DL-75 — useBreakpoint() is the responsive primitive for apps/mobile; ≥44px touch targets

**Date:** 2026-06-24
**Decided by:** Phil (CTO) during Phase CO-14
**Decision:** `apps/mobile/components/ui/use-breakpoint.ts` (`useBreakpoint()`, wrapping `useWindowDimensions`) is the standard primitive for responsive layout branches in the Expo app — it returns `{ width, isPhone (<640), isTablet (640–1023), isDesktop (≥1024) }`, the same 640/1024 cuts the web-marketing surface uses. Layout that must reflow by width (column-stack vs row, gutter/decoration sizing, full-width vs flex-1 tiles) branches on it rather than hardcoding a single (desktop) layout. Interactive controls target a **≥44px** hit area: a visible `min-h-[44px]` (usually with `items-center justify-center`) for buttons/pills, or `hitSlop` for deliberately-compact icon buttons (thumbs, citation chips, retry) where enlarging the visual would be wrong. The web-marketing surface additionally carries the viewport meta (`width=device-width, initialScale=1`) and token-only colors (no inline hex outside lucide icon color args).
**Reasoning:** the dashboard + flows were authored desktop-first; one primitive plus a single touch-target rule keeps every new screen mobile-correct without re-litigating breakpoints per component (CO-11 mobile-first convention).
**Reversibility:** the 640/1024 values and the 44px target are tunable; the "branch on useBreakpoint(), don't hardcode one layout" + ≥44px discipline is the locked convention.

## DL-76 — the Claude Agent SDK hook spine is wired into the agent loop

**Date:** 2026-06-24
**Decided by:** Phil (CTO) during Phase CO-15
**Decision:** The hook spine (fully implemented in `app/hooks/*` but previously invoked nowhere except a boot-time stub log) is now wired into the runtime agent loop. **Chat ingress** (`stream_chat_turn`, both fixture + real paths) runs the **crisis classifier** first — a positive signal returns the DL-04 Category-2 clean decline (no 988, no routing) and bypasses the Lead Planner entirely — then **UserPromptSubmit** (injection framing + a `block` short-circuit; the scrubbed message flows downstream). In the shared tool loop (`runner.run_agent`), **every tool call is wrapped by PreToolUse** (the sync `pre_tool_use_hook` decision — effective-date + approval-token gates; the audited `guard_send_email` path for `send_email` when a session is present, per the DL-65 split) — a block skips the call and feeds the reason back to the model — and **PostToolUse** writes a `tool_invocation` audit row. After each generation, the **Stop citation ship-gate** (`stop_hook`) resolves `[authority §sec, src_id]` markers against the run's retrieved chunks: ship, else regenerate (**≤3 attempts**) then `human_review` (surfaced on `RunResult`, not silently shipped). `run_agent` gains `case_file_id` / `actor` / `session`; the orchestrator opens one audit session per run and commits once (caller-commits, mirroring `guard_send_email`); with no session the decision hooks still run and audit WRITES are skipped with a warning (never a crash). **Production safety:** `allow_fixture_fallback` now defaults **false** and is **asserted false** (with `use_real_claude` true) at startup in production, so a missing/invalid key can never silently serve the MRI fixture ($560) as a real audit; and a real-agent run that produces no three-number finding returns a degraded `audit_incomplete` status (no `{0,0,0}`-complete). The **deep hook implementations** (Presidio arg-scrubbing, the crisis Haiku classifier, AES-GCM audit encryption) remain the security/HIPAA contact's Phase-4 drop-in **behind these now-connected call sites** — no further wiring needed when they land.
**Reasoning:** this was the #1 launch blocker from the codebase review — the Grounding, Independent-Audit, and crisis-decline doctrines were all inert because the loop called `call_tool` directly with no hooks. Wiring the integration seam (vs. building the deep impls) lets the security spine activate the real logic with zero additional runtime changes.
**Reversibility:** the regenerate cap (3) and the wiring (call-site placement, the DL-65 sync-decision / audited-send / audited-write split, the prod-safety assertion) are locked; the deep hook implementations are pending the security spine and swap in behind the unchanged interfaces.

## DL-77 — runtime CI gate (pytest + alembic upgrade-head + model/migration drift check); models reconciled to migrations

**Date:** 2026-06-24
**Decided by:** Phil (CTO) during Phase CO-16
**Decision:** The runtime (Python/FastAPI) gains its first CI gate (`.github/workflows/runtime-ci.yml`, path-filtered on `runtime/**`): a **tests** job (the full `pytest` suite + `ruff check` against a fresh Postgres service) and a **migrations** job (`alembic upgrade head` on an EMPTY DB — proves the chain applies from scratch — then `alembic check` — proves the SQLAlchemy models match the migrations, i.e. no schema drift). Previously nothing tested the runtime in CI; migrations were only applied against the LIVE dev DB at deploy time, so a broken chain or a model/migration drift would surface at deploy. To make `alembic check` green, the four models that had drifted from their migrations were **reconciled** (the migrations are authoritative + already correct — the models were the ones out of date): index `DESC` ordering restored (`idx_conversations_freeform`, `idx_conversations_user_id_updated_at`, `idx_cron_run_log_cron_name_started`, `idx_knowledge_gap_log_logged_at`), the missing partial indexes re-declared with `postgresql_where` (`idx_users_is_blocked`, `idx_knowledge_gap_log_unresolved`) plus the plain `idx_users_soft_deleted_at`, and the two self-referential `users` FKs given their migration names + `ondelete="SET NULL"` (`fk_users_blocked_by`, `fk_users_soft_deleted_by`). Also CO-16: the real Bill-Detective→Math-Person→Lead-Planner path is now exercised by a test (scripted Anthropic client; the fixture short-circuit had left it un-run) asserting the three-number audit shape end-to-end through the CO-15 hook spine.
**Reasoning:** the codebase review flagged both as P0 — the real agent path was untested (only the fixture short-circuit ran) and there was no schema-drift / migration-apply gate before the live deploy. A drift check is only useful if it's green, so the models were made to honestly describe the schema the migrations build.
**Reversibility:** the migrations stay authoritative for the DB; the models were aligned TO them (no DB change). The CI gate (pytest + upgrade-head + `alembic check`) is locked as the runtime pre-merge contract. A true VCR recording of the real agent path (vs the hand-authored scripted client) remains a follow-on.

## DL-78 — user-profile onboarding + insurance-card extraction; identified insurance_info kept separate from plan_library; card images in Blob

**Date:** 2026-06-27
**Decided by:** Phil (CTO) during Phase CO-17
**Decision:** Onboarding collects **name / date-of-birth / terms** onto `users` behind a `profile_completed` gate; the DOB is enforced **18+** (DL-17 — future or under-18 is a 422), and accepting terms sets `service_consent=true` while writing a `consent_history` audit row. The post-auth router reads `GET /v1/profile/state` and sends an incomplete user to onboarding **once** (DL-66 backfill marks all existing users incomplete — a deliberate re-collect, not silent grandfathering). Insurance cards are extracted with Azure's dedicated **`prebuilt-healthInsuranceCard.us`** model (stub fallback when OCR is off / creds missing) into **`insurance_info`** — ONE identified row per user (member id, names, DOBs, plan/payer/rx/medicare fields). The card **IMAGES go to Azure Blob** (the uploads container, served as a 15-min signed URL on Azure / streamed through the authed PHI-free route locally — DL-47), **never base64 in Postgres**; `insurance_cards` holds only a `blob_ref` + the per-side raw OCR, and a re-upload **replaces** the same side (UNIQUE(user_id, card_type)). The two sides are reconciled by preferring the higher-confidence non-null per field. **`insurance_info` (user-IDENTIFIED) is kept strictly separate from `plan_library` (plan-level, PHI-stripped, DL-73)** — the plan-level slice may later one-way-seed case coverage / a stripped PlanLibrary entry, never the reverse. Card upload **never 500s** on a bad scan (soft `extraction_status`). DEFAULTS: the insurance card is OPTIONAL at onboarding (required = name + DOB + terms); card images are RETAINED in Blob (not extract-and-discard).
**Reasoning:** profile + coverage onboarding is the on-ramp to a grounded audit (the user's real plan beats a generic assumption — Grounding Doctrine); keeping identified card data out of the shareable plan_library preserves the DL-73 PHI boundary, and keeping image bytes out of Postgres keeps the row PHI-light + cheap.
**Reversibility:** the Azure card field-name mapping is best-effort (validate against a real card — the project→map→merge structure is locked); the 18+ gate, the Blob-not-Postgres rule, the insurance_info≠plan_library separation, and replace-same-side are locked.
