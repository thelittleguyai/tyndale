# CLAUDE.md — Tyndale

Context file for Claude Code sessions working in this repository. Read this first. For
the full source spec see [`docs/tyndale-spec/`](docs/tyndale-spec/INDEX.md); for locked
decisions see [`docs/decision-log.md`](docs/decision-log.md); for the security/HIPAA
interface see [`docs/integration-contracts.md`](docs/integration-contracts.md).

## What Tyndale is

Tyndale is an AI medical-billing advocate. A user uploads a confusing bill, a denial, or a
stack of EOBs; Tyndale opens a case file and independently computes what the user should
owe from their actual coverage terms, the codes, the rules, and the law, then pursues every
gap it finds — on the provider's side and the insurer's side alike. Every factual, legal,
coverage, and pricing claim is grounded in authoritative data (CPT/HCPCS/ICD-10 catalogs,
NCCI/MUE tables, statutes, payer policies, the user's own documents), never the model's
memory, and Tyndale stays useful even when the user can't produce perfect inputs. Tyndale
audits both the provider's bill and the insurer's EOB independently and never trusts either.

## V1-Lite scope (ships first)

- **3 agents:** Lead Planner + Bill Detective + Math Person. The Legal Researcher's and
  Strategist's logic is folded into the Lead Planner; the Code Validator is deferred.
- **Document upload, not FHIR.** Users upload bills / EOBs / insurance card / plan summary;
  Azure Document Intelligence OCRs them. The `upload_extract_*` tools match the Full V1 FHIR
  tools' return shapes so subagents are source-agnostic.
- **No letter generation yet.** Tyndale gives the user a scripted phone call or letter to
  handle themselves instead of drafting and sending.
- **Feedback loop from day one.** Two-consent model + mandatory de-identification, so
  V1-Lite generates the labels that train Full V1.
- **Encounter verification** by translating each charged line item into plain language and
  asking the user to confirm what happened (facts about the visit, never clinical judgment).
- Forward-compatible with Full V1: same case-file schema, citation format, voice tiering,
  and tool return shapes. The upgrade is **expansion, not rewrite**.

## Full V1 (follows immediately after V1-Lite)

- Adds 3 more subagents: **Legal Researcher, Strategist, Code Validator**.
- Adds **FHIR via 1upHealth** (pulls coverage + EOBs + clinical notes automatically)
  alongside the upload path.
- Adds the **Document Generation Skill** (drafts the letter types) and a **gated
  `send_email` path** (PreToolUse approval gate before anything is sent).
- Promotes Negotiation & Strategy and Charity Care to standalone Skills. Manual human review
  of every appeal letter stays in place at V1.

## Architecture

- `intelligence-layer/` — Brock's authoring via Claude Code: Skills, subagent system
  prompts, tool descriptions, reference rules, collection schemas, eval data. Does not
  deploy; the runtime reads it.
- `runtime/` — Jonas's FastAPI monolith: tool implementations, hook wiring, Postgres
  models, routes, crons. Python project (not in the npm workspace).
- `apps/mobile/` — Phil's Expo React Native universal app (web + iOS + Android), the product.
- `apps/web-marketing/` — Next.js marketing/SEO landing, not the product.
- `packages/shared/` — TypeScript types shared across mobile, web-marketing, and the runtime
  API contracts.
- `infra/` — Terraform for Azure deployment (modules + per-env configs).

npm workspaces cover `apps/*` and `packages/*`. `runtime/` lives in the monorepo for
proximity but is a separate Python project.

## Security boundary

- **Secrets live only in the runtime environment.** Never expose anything sensitive through
  `NEXT_PUBLIC_*` or any client-bundled variable.
- **Claude runs through Azure AI Foundry (CO-18 / DL-79).** The runtime calls Claude via
  Foundry's Anthropic Messages API using its **managed identity** (no API key), so Azure's
  BAA covers Claude. `USE_FOUNDRY` selects that path in the single client factory
  (`runtime/app/agents/runner._client()`), and `assert_production_safety()` requires it in
  production — PHI must never route Anthropic-direct in prod. Anthropic-direct and the
  LiteLLM proxy remain config-gated dev/emergency fallbacks (precedence: Foundry → proxy →
  direct). Infra: `infra/envs/dev/ai_foundry.tf`.
- The **security/HIPAA infrastructure** — Presidio PHI scrubbing, encrypted audit log, Key
  Vault key rotation, the prompt-injection (UserPromptSubmit) hook, the citation Layer-2
  (Stop) hook, crisis classifier, LiteLLM proxy hardening, email approval gate, and BAA
  execution — is **built by a separate contact and tracked outside this repo's working
  plan**. This repo's only touchpoint is the interface contract in
  [`docs/integration-contracts.md`](docs/integration-contracts.md), which is the source of
  truth that contact builds against.
- Regulatory posture: non-HIPAA-covered consumer-health app under the FTC Act + FTC Health
  Breach Notification Rule + state privacy/health-data laws. Technical discipline
  (encryption, scrubbing, audit log, vendor BAAs) is unchanged; only the framing differs.

## The Independent Audit Doctrine (foundational — ranks above interaction style)

Neither the provider's bill nor the insurer's EOB is a source of truth; both are *claims*
made by parties whose work Tyndale is auditing. Tyndale independently computes what *should*
be true — from the user's actual coverage terms, the codes, the rules, and the law —
*before* looking at what the EOB claims, so the EOB cannot anchor the result, and then
compares that independent figure against both the bill and the EOB. Three numbers are
always reported: what the provider billed, what the payer's EOB claims the member owes, and
what Tyndale independently computes the member should owe; a gap with the EOB is a
payer-side finding, a gap with the bill is a provider-side finding, and both are pursued
with equal rigor. Tyndale never reads the EOB's "member responsibility" figure back to the
user as if it were correct, and never treats a charge as legitimate just because it appears
on the bill.

## The Grounding & Graceful Degradation Doctrine (foundational)

Everything Tyndale asserts is grounded in authoritative data — a retrieved source, a
structured table, the user's own documents, or a computation over those — and the model's
training-data recall is never the basis for a factual, legal, coverage, or pricing claim;
this is what makes Tyndale superior to a general LLM for billing the way a data-grounded
clinical tool beats a general model at diagnosis. Tyndale reaches for the most authoritative
and most specific source available (structured tables over narrative for code rules; statute
over summary for law; the user's actual plan over a generic assumption) and is transparent
about which source backs each claim, saying so explicitly when it must fall back to a weaker
substitute. Incomplete data narrows the answer but never dead-ends the user: Tyndale does
the most it can with what it has, states plainly what it cannot yet conclude, and helps the
user get the missing piece — climbing the degradation ladder (full → partial → minimal data)
while delivering real value at every rung rather than refusing until inputs are perfect.

## Voice tiering (tier discipline)

- **Tier A — facts.** Asserted plainly, sourced only from structured inputs.
- **Tier B — legal/coverage claims.** Always carry an inline citation and a standard
  confident qualifier.
- **Tier C — strategic recommendations.** Stated with the reasoning, not just an
  instruction; recommend one path and note alternatives rather than handing the user a menu.
- **Forbidden: predicting outcomes.** Genuine uncertainty is named specifically rather than
  hedged.

## Out-of-scope: crisis decline

Mental-health crisis input gets a **clean refusal with no 988 referral and no routing of any
kind**. A Haiku 4.5 classifier screens chat input before normal processing; a positive
signal triggers the decline immediately, bypassing the Lead Planner. Tyndale is a
medical-billing advocacy/reconciliation platform, not a crisis center. (All five
out-of-scope categories use clean declines that emphasize what Tyndale *does* handle — see
the refusal templates in `docs/tyndale-spec/`.)

## UI design directive

ALL UI in Tyndale — every signed-out marketing page, every signed-in screen in
`apps/mobile`, every modal, every email template, every future feature — follows the design
theme established in:

- `docs/design/marketing_landing.png`
- `docs/design/signed_in_dashboard.png`

These screenshots are the canonical visual reference. The Tailwind design tokens in
`packages/shared/src/design-tokens.ts` encode the palette and typography; CLAUDE.md treats
the screenshots as the source of truth where tokens and screenshots disagree.

When building any new UI surface, future Claude Code sessions read both screenshots before
writing components. New screens use the same dark navy/teal + cream-light palette, the same
Inter typography, the same rounded-card primitives, the same sage/amber/rose accents, and the
same component conventions visible in the screenshots.

This directive is permanent. It supersedes any per-prompt UI guidance that contradicts it.

## Phase status

Phase 0 closure complete: monorepo skeleton, root configs, docs scaffold, integration
contracts published, source spec imported.

Operational: BAA tracker at intelligence-layer/operational/baa_tracker.md.

Decision log canonical: DL-01 through DL-63 in docs/decision-log.md.
Cowork numbers DL-NN-style entries chronologically as decisions land.
CO-002 FINAL approved 2026-05-30; Sprint A in flight.

## Terminology (DL-91)

In code, a **`case`** (the `case_files` row / `case_file_id`) is what the product calls a
**sub-case** — one uploaded bill/EOB set and its audit. The user-level **"Tyndale Record"** view
that groups a person's sub-cases is **Phase C** (design decision D5), built behind
`ENABLE_RECORD_VIEW` (default false, independent of `ENABLE_CHAT_FIRST_AUDIT`): `GET /v1/record`,
the sub-case summary at `GET /v1/case/{id}/summary` + mobile `/case/{id}` (with the gameplan and
call mode), and the `/audit/{id}` deep-link redirects. Flag-off is a no-op (the classic dashboard
is unchanged). When writing product-facing copy, say "sub-case"; in code and comments, `case` is
fine.

The **chat-first audit flow** (DL-91) is Phase A behind `ENABLE_CHAT_FIRST_AUDIT` (default false).
The classic screen flow is fully retained and unchanged when the flag is off — flag-off *is* the
transition (D7). All system-authored thread copy lives in
`intelligence-layer/prompts/orchestration_script.md` (Brock's authoring; engineering seeds
`[PLACEHOLDER-eng]` values that a staging/production boot rejects).
