# Phase 0 Closure — Claude Code Prompt

**For:** Phil (to paste into a fresh Claude Code session)
**Goal:** Execute Phase 0 exit criteria — initialize `tyndale.git` with the monorepo skeleton, root configs, CLAUDE.md, README, decision log, integration contracts, and a copy of the spec docs. Two clean commits. Do not push until Phil reviews.

After Claude Code reports back, Cowork issues the Phase 1 prompts.

---

## How to run

1. Open a fresh Claude Code session in your code parent directory (e.g., `cd ~/code`)
2. Copy everything between the `BEGIN` and `END` markers below
3. Paste into Claude Code
4. Review the two commits when it reports back; push manually if everything looks right

---

```
BEGIN — Phase 0 Closure Prompt

You are setting up Tyndale's monorepo per the approved Phase 0 spec.

CONTEXT
- Tyndale is an AI medical-billing advocate that audits both the provider bill and the
  insurer's EOB independently and never trusts either. V1-Lite ships first (3 agents,
  document upload, no letter generation, feedback loop from day one), then Full V1
  begins immediately after launch.
- Tech stack: React Native + Expo (universal web + iOS + Android), Next.js for marketing,
  FastAPI runtime, self-hosted Qdrant in Azure VPC, deployed to Azure via Terraform.
- Regulatory posture: non-HIPAA-covered consumer-health app under FTC Act + FTC Health
  Breach Notification Rule + state privacy/health-data laws.
- The full spec lives in two folders on this machine:
  - /Users/phil/Tyndale V3/Tyndale Final/ (47 files)
  - /Users/phil/Tyndale V3/Additional Files/ (7 files)
- This Phase 0 closure does NOT write production code. It scaffolds directories,
  root configs, and documentation only.

STEP 1 — CLONE AND VERIFY

1. Clone git@github.com:thelittleguyai/tyndale.git into ./tyndale in the current parent
   directory.
2. cd into ./tyndale.
3. Verify the repo is empty (only .git, maybe a stub README/LICENSE). If you find prior
   work, STOP and show me what's there — do not modify anything until I confirm.

STEP 2 — ROOT CONFIGURATION FILES

Create these at the repo root:

- .gitignore: node_modules, .next, dist, build, .turbo, coverage, .env, .env.local,
  .env.*.local, .DS_Store, *.log, __pycache__, *.pyc, .pytest_cache, .venv, .vscode,
  .idea, *.swp, .terraform, *.tfstate*, .terragrunt-cache
- .editorconfig: root=true; UTF-8; LF line endings; trim trailing whitespace; final
  newline; 2-space indent for all files; 4-space indent for *.py.
- .nvmrc: just the line "20".
- package.json (npm workspaces root):
    {
      "name": "tyndale",
      "private": true,
      "workspaces": ["apps/*", "packages/*"],
      "scripts": {
        "lint": "echo 'lint placeholder'",
        "typecheck": "echo 'typecheck placeholder'",
        "test": "echo 'test placeholder'"
      },
      "engines": { "node": ">=20" }
    }
- tsconfig.base.json:
    {
      "compilerOptions": {
        "target": "ES2022",
        "module": "ESNext",
        "moduleResolution": "Bundler",
        "strict": true,
        "esModuleInterop": true,
        "skipLibCheck": true,
        "forceConsistentCasingInFileNames": true,
        "resolveJsonModule": true,
        "isolatedModules": true,
        "baseUrl": ".",
        "paths": {
          "@tyndale/shared": ["./packages/shared/src"]
        }
      }
    }

STEP 3 — DIRECTORY SCAFFOLD

Create this directory tree using `mkdir -p` (do not create any source files yet, just
directories with .gitkeep placeholders):

  intelligence-layer/
    reference/
    skills/
    subagents/
    tools/descriptions/
    collections/{schemas,ingestion,fixtures}
    evals/{golden,synthetic}
    operational/
  runtime/
    app/
      agents/
      tools/
      hooks/
      routes/
      db/
      middleware/
      config/
      stubs/
    crons/
    tests/
  apps/
    mobile/
    web-marketing/
  packages/
    shared/src/
  infra/
    modules/
    envs/{dev,staging,production}/
  docs/
    tyndale-spec/
  .github/workflows/

Add a `.gitkeep` file in every leaf directory so git tracks them.

STEP 4 — CLAUDE.md

Write CLAUDE.md at the root. Future Claude Code sessions in this repo read this first.
Include:
- One-paragraph product description ending with: "Tyndale audits both the provider's bill
  and the insurer's EOB independently and never trusts either."
- V1-Lite scope: 3 agents (Lead Planner + Bill Detective + Math Person), document upload
  (not FHIR), no letter generation yet, feedback loop from day one. Forward-compatible
  with Full V1.
- Full V1 follow-on: ships immediately after V1-Lite. Adds 3 more subagents (Legal
  Researcher, Strategist, Code Validator), FHIR via 1upHealth, Document Generation Skill,
  gated send_email path.
- Architecture overview: `intelligence-layer/` (Brock's authoring via Claude Code), `runtime/`
  (FastAPI + tool implementations + hook wiring), `apps/mobile/` (Expo RN universal),
  `apps/web-marketing/` (Next.js), `packages/shared/` (TS types), `infra/` (Terraform).
- Security boundary: secrets only in runtime env. No NEXT_PUBLIC_* for anything sensitive.
  Security/HIPAA infrastructure (Presidio scrubbing, encrypted audit log, key rotation,
  prompt-injection hook, LiteLLM proxy hardening, BAA execution) is built by a separate
  contact and tracked outside this repo's working plan; integration contracts in
  `docs/integration-contracts.md`.
- The Independent Audit Doctrine in one paragraph (audit both bill and EOB; three numbers;
  never read the EOB's "member responsibility" back as if it were correct).
- The Grounding & Graceful Degradation Doctrine in one paragraph.
- Tier discipline (A facts, B legal with citation, C strategic recommendation with
  reasoning; never predict outcomes).
- Crisis decline: clean refusal, no 988 referral, no routing of any kind. Tyndale is a
  medical-billing advocacy/reconciliation platform, not a crisis center.
- Phase status section at the bottom: "Phase 0 closure complete: monorepo skeleton, root
  configs, docs scaffold, integration contracts published, source spec imported."

STEP 5 — README.md placeholder

Write README.md at the root. Quickstart-style. Should include:
- One-sentence product line
- Repo layout (the top-level directories from Step 3)
- Phase status (Phase 0 closure complete; Phase 1 begins next)
- Quickstart: how to clone, install deps, and run the apps once they exist (placeholder
  for now since the apps are empty)
- Pointer to CLAUDE.md for product context and `docs/tyndale-spec/` for the full spec

STEP 6 — docs/decision-log.md

Write docs/decision-log.md capturing every locked decision from the parent build plan
and Phase 0 spec. Use this structure for each entry:

  ## DL-NN — {Decision title}
  **Date:** 2026-05-27
  **Decided by:** {Brock | Phil (CTO)}
  **Decision:** {one-paragraph statement of what was decided}
  **Reasoning:** {one-paragraph context}
  **Reversibility:** {locked | revisable with cause}

Include at minimum these entries:
- DL-01: V1-Lite ships first, Full V1 immediately after — Brock
- DL-02: Single brand with beta framing — Brock (from docs, reaffirmed)
- DL-03: National launch, all 50 states — Brock
- DL-04: Crisis decline with no routing of any kind reaffirmed — Brock
- DL-05: Non-HIPAA-covered consumer-health-app posture (FTC + state laws) — Brock, pending
  counsel confirmation
- DL-06: Tech stack — React Native + Expo (universal) + Next.js marketing landing — Phil
- DL-07: Single monorepo in tyndale.git — Phil
- DL-08: Walking-skeleton build sequencing — Phil
- DL-09: Plausible for analytics; no advertising/retargeting trackers anywhere — Phil
- DL-10: Free-tier abuse — email + phone verification + Terms Section 8 — Phil
- DL-11: Security/HIPAA infrastructure built by Brock's contact, tracked outside this
  plan; integration contracts only — Brock
- DL-12: Apple Sign-In: fast-follow at native iOS App Store submission, not V1-Lite web
  launch — Brock
- DL-13: Change Order 001 (4 behavioral additions) accepted into V1-Lite — Brock
- DL-14: Post-V1-Lite agent-company vision parked; revisit after Full V1 stabilizes — Brock
- DL-15: Legal entity is The Little Guy LLC d/b/a Tyndale (Utah); governing law Utah —
  per legal pack
- DL-16: Pricing locked — $11.99/mo or $100/yr unlimited; free tier = one bill analysis;
  cancel at end of period; no prorated refunds — per legal pack
- DL-17: 18+ US-only; parent/guardian managing minor's bills permitted — per legal pack
- DL-18: Domain tyndaleapp.net; SendGrid Email API Pro (HIPAA-eligible tier) for sends —
  Phil + Brock
- DL-19: Counsel engagement + dev team capacity managed outside Cowork — Brock

Keep each entry brief — one paragraph per Reasoning. The log is searchable history, not
a research paper.

STEP 7 — docs/integration-contracts.md

The integration contracts for the security/HIPAA spine are in Section 2 of
/Users/phil/Tyndale V3/Tyndale Final/01_phase0_detailed_spec.md.

Extract Section 2 verbatim (subsections 2.1 Hook signatures, 2.2 Audit log payload
schema, 2.3 Case file schema with research_log, 2.4 Feedback handoff) into
docs/integration-contracts.md. Add a header that names this as the contract surface
Brock's security/HIPAA contact builds against and points the contact to this file as
the source of truth.

STEP 8 — docs/tyndale-spec/ + INDEX

Copy all files from /Users/phil/Tyndale V3/Tyndale Final/ and /Users/phil/Tyndale V3/Additional Files/
into docs/tyndale-spec/. Both source folders are flat — preserve filenames verbatim. If
there's a collision (there shouldn't be), prepend "additional_" to the file from
Additional Files/.

Create docs/tyndale-spec/INDEX.md grouping the imported files into these sections, each
file with a one-line description:

  ## Acceptance narrative
  - how_tyndale_works_reference.md

  ## Foundation & cross-cutting reference rules
  - 02_principles.md
  - 03_voice_tiering.md
  - 04_refusal_templates.md
  - 05_citation_format.md
  - 06_tyndale_glossary.md
  - 07_discipline_rules.md

  ## V1-Lite track
  - 01_v1lite_scope_and_compatibility.html
  - 02_v1lite_build_kit_index.html
  - L01_orientation.md through L09_v1lite_handoff.md

  ## Full V1 build kit (overview + 32 tasks)
  - 01_overview.html
  - 02_developer_spec.html
  - 03_build_kit_index.html
  - 01_repo_setup.md
  - 08_skill_bill_error_detection.md through 15_skill_plan_a_visit.md
  - 16_subagent_lead_planner.md through 21_subagent_code_validator.md
  - 22_tool_descriptions.md
  - 23_collection_schemas.md through 29_synthetic_generation_runner.md
  - 30_readme.md
  - 31_baa_tracker.md
  - 32_handoff_brief.md

  ## Cowork PM/PdM outputs
  - 00_v1lite_build_plan_for_brock_approval.md
  - 01_phase0_detailed_spec.md
  - 02_phase0_closure_prompt.md (this file)

  ## Legal pack + change orders (from Additional Files/)
  - 00_developer_cowork_notes.md
  - 01_terms_of_service.md
  - 02_privacy_policy.md
  - 03_improvement_consent.md
  - 04_state_specific_rights_addendum.md
  - change_order_001_readds.md
  - post_v1lite_agent_architecture_vision.md

STEP 9 — VERIFY

1. Run `git status` to confirm all expected files are present
2. Run `npm install` at the root (workspaces will bootstrap; minimal work to do now)
3. Run `find . -maxdepth 3 -type d | sort` and confirm the directory tree matches Step 3
4. Confirm no .env files, no secrets, no source code under apps/ or runtime/ beyond
   .gitkeep placeholders

STEP 10 — TWO COMMITS

Commit 1 (structure):
  git add .gitignore .editorconfig .nvmrc package.json tsconfig.base.json
  git add intelligence-layer/ runtime/ apps/ packages/ infra/ .github/
  git commit -m "chore: initial monorepo skeleton (Phase 0)"

Commit 2 (docs):
  git add CLAUDE.md README.md docs/
  git commit -m "docs: import Tyndale spec, integration contracts, and decision log"

DO NOT PUSH. Show me the commit log and the directory tree, and let me review before
pushing to remote.

STEP 11 — REPORT BACK

In your reply, include:
- `git log --oneline` (last 5 entries)
- `find . -maxdepth 3 -type d | sort` output
- The size of docs/tyndale-spec/ (number of files copied)
- Any deviations from this prompt and why
- Anything that needs my attention before I push

DO NOT proceed beyond this prompt. After I confirm the two commits look right and push
to remote, Cowork will send the Phase 1 prompts.

END — Phase 0 Closure Prompt
```

---

## What happens after Phase 0 closure

Once Phil reviews and pushes the two commits, Cowork sends four parallel Phase 1 prompts:

- **Phase 1A** — Brock's intelligence-layer foundation files (build kit Tasks 01–07: principles incorporating Change Order 001's always-loaded behavioral core + thinking loop, voice tiering, refusal templates, citations, glossary, discipline rules). Brock runs this in his own Claude Code session against `intelligence-layer/`.
- **Phase 1B** — Phil's frontend scaffold (Expo project init, Tyndale design system, Next.js marketing landing, Plausible wired up, Google + Email auth scaffold, "SCAFFOLD — not for real PHI" banner).
- **Phase 1C** — Jonas's runtime skeleton (FastAPI scaffold, Postgres schema per the integration contracts including case files with `research_log`, health/readiness routes, LiteLLM proxy skeleton).
- **Phase 1D** — Josh's knowledge layer (self-hosted Qdrant in Azure VPC, four empty collections with metadata schemas locked, embedding client setup).

The four can run in parallel once Phase 0 closure lands; Cowork will hand them out as Phil signals each owner is ready.

## Parallel reminders (out-of-Cowork, Brock's ownership)

These should be moving in parallel as Phase 1 kicks off. Cowork flags if any aren't progressing in time for the indicated phase:

- Counsel engagement and legal-pack review (blocks Phase 7 publication)
- AMA CPT license procurement (blocks Phase 5 `billing_codes` ingestion)
- FAIR Health license procurement (blocks Phase 5 Cost Estimation accuracy; Medicare-RVU fallback works)
- Anthropic + Azure + AWS BAAs (block Phase 4 PHI spine integration)
- SendGrid Email API Pro tier + BAA (blocks Phase 1 account/notification email)
- Voyage AI BAA (blocks Phase 5 embedding work on user content if applicable)
- Stripe BAA (blocks Phase 4 Stripe integration)
- Observability vendor BAA (blocks Phase 1 monitoring setup)
- Azure tenancy provisioning (blocks Phase 1 deploys)
- Apple Developer enrollment + Services ID (parallel during Phases 2–4 for the native iOS App Store submission)
- Security/HIPAA contact engaged and reading `docs/integration-contracts.md` (blocks Phase 4)

Status updates on these flow through Brock; Cowork records them in `docs/decision-log.md` as they land.
