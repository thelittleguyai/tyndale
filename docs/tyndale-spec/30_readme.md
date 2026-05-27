# Task 30 — Write the project README

**Phase:** 7 · Documentation
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** All previous phases

## What this task does

Replaces the placeholder README.md from Task 01 with a comprehensive project README. This is what Phil, Jonas, and Josh see first when they clone the repo.

## Prompt to paste into Claude Code

```
Replace the placeholder README.md at the root of this repository with a
comprehensive project README.

Use this structure:

# Tyndale Intelligence Layer

The non-runtime portion of Tyndale's AI brain — prompts, Skills, tool
descriptions, knowledge collection scaffolding, and eval test data.

## What this repository is

Tyndale is an AI-powered medical billing reconciliation and health
advocacy platform. The intelligence layer is the AI brain — Lead
Planner + 5 subagents + 8 Skills + 4 Qdrant knowledge collections.

This repository holds the parts of the intelligence layer that don't
require a running production system to author:

- `reference/` — cross-cutting principles, voice tiering, refusals,
  citations, glossary, discipline rules
- `skills/` — 8 Skills with SKILL.md + reference files + diagnostic indexes
- `subagents/` — 6 subagent system prompts (Lead Planner + 5 specialists)
- `tools/descriptions/` — descriptions for ~27 tools
- `collections/` — schemas, ingestion templates, test fixtures
- `evals/` — golden examples + synthetic adversarial cases
- `operational/` — BAA tracker, handoff brief

The runtime — FastAPI monolith, LiteLLM proxy, Qdrant deployment,
Postgres schemas, FHIR OAuth, hooks, Stripe — lives in a separate
repository owned by the engineering team.

## How this repository was built

Brock built this using the Claude Code build kit (build_kit/), which
sequenced 32 tasks across 7 phases. Each task produced specific files
in this repo. The build kit document explains why each piece exists
and how it should evolve.

## Architecture at a glance

```
                       USER
                         ↓
                   LEAD PLANNER (Sonnet 4.6)
                  /     |     |    |     \
            Bill   Math  Legal  Strat   Code
           Detect  Person Resrch  egist  Valid
          (Sonnet)(Sonnet)(Sonnet)(Opus)(Haiku)
              ↓     ↓      ↓      ↓      ↓
               consult Skills as needed
              ↓     ↓      ↓      ↓      ↓
              4 Qdrant collections + Postgres
```

8 Skills:
- Document Generation (21 letter types)
- Cost Estimation
- Bill Error Detection (+ diagnostic index)
- Coverage Connection & FHIR
- Find a Doctor
- Plan a Visit
- Charity Care Eligibility (+ diagnostic index)
- Negotiation & Strategy (+ diagnostic index)

4 knowledge collections:
- billing_codes (~80K codes)
- error_detection_rules (~250K rule narratives)
- laws_regulations (~12K statute chunks)
- payer_policies (~30K policy chunks)

## Foundation files everything references

Before reading any Skill or subagent prompt, read these:

- `reference/principles.md` — six operating principles P1–P6
- `reference/voice_tiering.md` — three-tier voice framework
- `reference/refusals.md` — five out-of-scope categories
- `reference/citations.md` — standard citation format + source IDs
- `reference/glossary.md` — standard terms for codes, payers, statutes
- `reference/discipline_rules.md` — every rule from the 22 decisions

## Getting started (for Phil, Jonas, Josh)

1. Read `operational/handoff_brief.md` first — it explains what's
   built here and what you need to build in the runtime repo.

2. Read the developer build spec (delivered separately as
   `02_developer_spec.html`) for the full technical architecture.

3. Read `reference/discipline_rules.md` for the consolidated set of
   hard rules across all 22 decisions.

4. For your area of focus:
   - Phil (frontend): start with the user flow documents and the
     case-file artifact pattern in section 12 of the developer spec
   - Jonas (Python/Postgres/FastAPI): start with sections 11 (tools),
     12 (context management), 16 (LiteLLM routing), and 18 (PHI/logging)
     of the developer spec
   - Josh (Qdrant/RAG): start with sections 06 (collections),
     07 (embeddings), 08 (hybrid search/chunking), and 09 (vector DB)
     of the developer spec

## Decision log

The 22 architectural decisions that define this system are documented
in the developer build spec (delivered separately). When you need to
understand WHY something is the way it is, check that document. The
discipline rules in `reference/discipline_rules.md` reference the
decision numbers (D2–D22).

## What's NOT in this repo

- Runtime application code (FastAPI app, LiteLLM proxy config, hooks
  implementation) → separate engineering repo
- Production knowledge data (the actual 80K billing codes, etc.) →
  ingested via scripts in `collections/ingestion/`
- Secrets, API keys, BAA-protected documents → never in any repo
- Compiled output, build artifacts → see .gitignore

## Versioning

- Skills: semver in YAML frontmatter (e.g., 1.0.0)
- Subagent prompts: semver in CHANGELOG.md per subagent directory
- Collection schemas: schema version field within the JSON
- This repo overall: tagged releases align with milestone deliveries
  (V1.0 = pre-launch ship)

## Contributing

For now, contributions to this repo flow through Brock. After V1
launch, the engineering team will own the runtime repo and Brock will
remain the primary author of Skill prompts, subagent prompts, and
reference files. Updates from the team to prompts/Skills go via PR with
two-person review (per discipline rule D22.7).

## Contact

[Brock's contact info]

Commit with message "Add comprehensive project README".
```

## Done when

`README.md` at the repo root has the full content. Git log shows the commit.

## Next task

[Task 31 — BAA tracker](31_baa_tracker.md)
