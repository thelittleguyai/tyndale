# Phase 1D — Qdrant Knowledge Layer · Claude Code Prompt

**For:** Phil or Josh (knowledge-layer track) — paste into a fresh Claude Code session at `~/code/tyndale`
**Goal:** Stand up a self-hosted Qdrant instance (local Docker first), create the four V1-Lite knowledge collections with locked metadata schemas, set up the Voyage AI embedding client, and seed each collection with fixtures from build kit Task 25 so the runtime has something to query against.

**Prerequisites:** Phase 0 closure pushed. Phase 1A, 1B, 1C are independent. Azure tenancy provisioning (Brock's parallel track) is NOT required for Phase 1D — local Docker first; Azure deploy follows when tenancy lands.

**Output:** Local Qdrant via Docker Compose, four collections initialized with schemas locked, fixtures seeded, embedding client tested end-to-end. One commit.

---

## How to run

1. Confirm Phase 0 closure is on `main`
2. Open a fresh Claude Code session in `~/code/tyndale`
3. Copy everything between the `BEGIN` and `END` markers below
4. Paste into Claude Code
5. Review the commit and confirm local Qdrant returns hits on a sample query; push manually

---

```
BEGIN — Phase 1D Prompt

You are scaffolding Tyndale's knowledge layer — the four Qdrant collections
that hold the reference data Tyndale grounds its claims in. Local Docker
deployment for now; production Azure VPC deployment is parallel-track and
follows when Brock's Azure tenancy is provisioned.

CONTEXT
- Four collections per the developer spec §6 and locked schemas in
  docs/tyndale-spec/23_collection_schemas.md:
  - billing_codes  (CPT/HCPCS/ICD-10 — ~80K rows at production; ~20 fixtures
    now per docs/tyndale-spec/25_test_fixtures.md)
  - error_detection_rules  (NCCI/MUE narrative + ACA preventive list + upcoding
    patterns; ~250K at production; ~20 fixtures now)
  - laws_regulations  (ERISA, ACA, NSA, MHPAEA, IRS §501(r), state laws; ~12K
    at production; ~20 fixtures now)
  - payer_policies  (CMS LCDs/NCDs + commercial medical-necessity policies;
    ~30K at production; ~20 fixtures now)
- Embeddings per docs/tyndale-spec/02_developer_spec.html §7 (locked):
  - billing_codes → voyage-3-large, dim 1024, int8
  - error_detection_rules → voyage-3-large, dim 1024, int8
  - laws_regulations → voyage-context-3, dim 1024, int8
    (Note: the voyage-context-3 vs voyage-3-large NDCG benchmark is Phase 5,
    Josh's ship-gate work. For Phase 1D, default to voyage-context-3 since the
    spec lists it as the working choice unless the benchmark says otherwise.)
  - payer_policies → voyage-3-large, dim 1024, int8
- Hybrid search (vector + BM25 with RRF) on all four collections per §8.
- Mandatory point-in-time filters on laws_regulations and payer_policies per
  §6 — each chunk has effective_date_start and effective_date_end; every
  query filters by date-of-service.
- NCCI and MUE tabular rules go in Postgres, NOT Qdrant — only the narrative
  policy text goes into error_detection_rules. (The Postgres tables are
  scaffolded in Phase 1C; Phase 1D doesn't touch them.)
- Reranking via voyage rerank-2.5 on all RAG queries — set up the client but
  per-collection rerank instruction tuning is deferred to Phase 5.
- Voyage AI BAA status: tracked by Brock outside this plan. For Phase 1D
  fixtures (no real PHI), Voyage usage is fine.

OUTPUTS

  runtime/                       (additions to the existing Phase 1C scaffold)
    docker-compose.yml           (add a qdrant service)
    .env.example                 (add QDRANT_URL, QDRANT_API_KEY, VOYAGE_API_KEY)
    app/
      knowledge/
        __init__.py
        client.py                — Qdrant client wrapper, env-aware
        embeddings.py            — Voyage AI embedding client
        rerank.py                — Voyage AI rerank client (used in Phase 2+)
        collections.py           — collection schemas + create_collection logic
        search.py                — hybrid search wrapper with date-filter
                                   enforcement on laws/policies
    scripts/
      init_collections.py        — idempotent: ensure all 4 collections exist
                                   with locked schemas
      seed_fixtures.py           — load fixtures from docs/tyndale-spec/ into
                                   the local Qdrant
      benchmark_recall.py        — placeholder for the Phase 5 NDCG benchmark
                                   (just prints "TODO Phase 5" for now)

  intelligence-layer/collections/  (already scaffolded as empty dirs in Phase 0)
    schemas/
      billing_codes.json         — JSON Schema per docs/tyndale-spec/23
      error_detection_rules.json
      laws_regulations.json
      payer_policies.json
    rerank_instructions.md       — per-collection default instructions per the
                                   developer spec §7 (defaults; tuning in Phase 5)
    fixtures/
      billing_codes.json         — ~20 records from docs/tyndale-spec/25
      error_detection_rules.json
      laws_regulations.json
      payer_policies.json
      README.md

STEP 1 — docker-compose.yml addition

Add a qdrant service to the existing runtime/docker-compose.yml:

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - 6333:6333    # HTTP
      - 6334:6334    # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}

Add `qdrant_data` to the volumes block at the bottom.

STEP 2 — .env.example additions

Add to runtime/.env.example:

  # Qdrant (local dev)
  QDRANT_URL=http://localhost:6333
  QDRANT_API_KEY=dev_local_only_change_in_prod

  # Voyage AI (embeddings + reranking)
  VOYAGE_API_KEY=

  # Embedding model overrides (defaults are locked; override only for benchmarks)
  EMBEDDING_MODEL_BILLING_CODES=voyage-3-large
  EMBEDDING_MODEL_ERROR_DETECTION=voyage-3-large
  EMBEDDING_MODEL_LAWS=voyage-context-3
  EMBEDDING_MODEL_PAYER_POLICIES=voyage-3-large

STEP 3 — Collection JSON schemas

Read docs/tyndale-spec/23_collection_schemas.md fully. For each of the four
collections, write a JSON Schema (draft-07) file under
intelligence-layer/collections/schemas/ matching the field specifications.

Each schema must validate:
- Required fields per the spec
- Effective-date fields as ISO 8601 date strings
- Enum constraints (code_system: CPT|HCPCS|ICD-10; document_type:
  statute|regulation|sub_regulatory_guidance; plan_type:
  commercial|Medicare|Medicaid; jurisdiction: federal|state_<XX>)
- last_verified_date on laws_regulations and payer_policies (set by the
  Regulation Researcher cron in Phase 5)

Include an example record at the bottom of each JSON file.

STEP 4 — rerank_instructions.md

Read docs/tyndale-spec/02_developer_spec.html §7 ("Default rerank instructions")
and copy the per-collection instructions verbatim into
intelligence-layer/collections/rerank_instructions.md. These are the defaults;
subagents can override per query in Phase 2.

STEP 5 — Fixtures

Read docs/tyndale-spec/25_test_fixtures.md fully. It specifies ~20 records per
collection with realistic, diverse content. Generate the four JSON fixture
files under intelligence-layer/collections/fixtures/ following its guidance.

Copyright caveats from the spec:
- billing_codes: use generic descriptors close to but NOT verbatim from the
  CPT codebook (AMA-owned).
- error_detection_rules: paraphrase policy text, not verbatim.
- laws_regulations: federal statutes/regulations are public domain — verbatim
  is fine for these.
- payer_policies: clearly-synthesized examples, not real verbatim policies.

Each fixture file is a JSON array of records validating against the
corresponding schema from Step 3. Add a top-level "_meta" comment block in
each file marking it as fixture data and noting the date.

Add intelligence-layer/collections/fixtures/README.md explaining: fixtures
are for local dev only; production ingestion in Phase 5 uses the ingestion
templates at docs/tyndale-spec/24_ingestion_templates.md.

STEP 6 — app/knowledge/client.py

Qdrant async client wrapper. Reads QDRANT_URL and QDRANT_API_KEY from config.
Exposes:
- get_client() — singleton async client
- ensure_collection(name, vector_size, distance, hybrid_enabled=True) —
  idempotent create-if-not-exists with the locked schema

STEP 7 — app/knowledge/embeddings.py

Voyage AI embedding client. Reads VOYAGE_API_KEY. Exposes:
- embed(text: str, model: str) -> list[float]
- embed_batch(texts: list[str], model: str) -> list[list[float]]
- Model resolution from env (EMBEDDING_MODEL_* vars per collection)

Quantization to int8 happens at upsert time (Qdrant does this on the server
side when configured); collection config sets quantization=int8.

STEP 8 — app/knowledge/rerank.py

Voyage rerank-2.5 client. Reads VOYAGE_API_KEY. Exposes:
- rerank(query: str, documents: list[str], top_n: int, instruction: str |
  None = None) -> list[RerankResult]

Per-collection default instructions loaded from
intelligence-layer/collections/rerank_instructions.md at startup.

STEP 9 — app/knowledge/collections.py

Define the four collection configs as Python constants:

  COLLECTIONS = {
    "billing_codes": CollectionConfig(
      vector_size=1024,
      distance=Distance.COSINE,
      quantization="int8",
      embedding_model="voyage-3-large",
      hybrid_enabled=True,
      requires_effective_date_filter=False,
    ),
    "error_detection_rules": CollectionConfig(
      vector_size=1024,
      distance=Distance.COSINE,
      quantization="int8",
      embedding_model="voyage-3-large",
      hybrid_enabled=True,
      requires_effective_date_filter=False,
    ),
    "laws_regulations": CollectionConfig(
      vector_size=1024,
      distance=Distance.COSINE,
      quantization="int8",
      embedding_model="voyage-context-3",
      hybrid_enabled=True,
      requires_effective_date_filter=True,
    ),
    "payer_policies": CollectionConfig(
      vector_size=1024,
      distance=Distance.COSINE,
      quantization="int8",
      embedding_model="voyage-3-large",
      hybrid_enabled=True,
      requires_effective_date_filter=True,
    ),
  }

STEP 10 — app/knowledge/search.py

Hybrid search wrapper. Two operations:

  search(collection: str, query: str, effective_date: date | None = None,
         filters: dict | None = None, top_k: int = 50) -> list[Hit]

- If COLLECTIONS[collection].requires_effective_date_filter and effective_date
  is None: raise ValueError("effective_date filter required for this
  collection"). The PreToolUse hook (Phase 1C stub; Phase 4 real) also enforces
  this — defense in depth.
- Embed the query using the collection's configured model.
- Run hybrid query (vector + BM25 with RRF fusion, default 0.5/0.5).
- Return top_k=50 hits with their payloads and rerank scores.

  search_and_rerank(collection: str, query: str, ..., top_n: int = 10) -> list[Hit]

- Calls search() to get top_k=50.
- Calls rerank.rerank() with the collection's default instruction.
- Returns top_n.

STEP 11 — scripts/init_collections.py

Idempotent script: for each collection in COLLECTIONS, ensure_collection() on
the Qdrant instance. Logs created vs. already-exists per collection. Safe to
run multiple times.

Usage: `uv run python scripts/init_collections.py`

STEP 12 — scripts/seed_fixtures.py

Read each fixture JSON file from intelligence-layer/collections/fixtures/.
Validate each record against the corresponding JSON Schema. For each valid
record:
- Generate an embedding using the collection's configured model
- Upsert to Qdrant with the record's metadata as payload

Log totals per collection. Skip records that fail validation with a clear
error message.

Usage: `uv run python scripts/seed_fixtures.py`

STEP 13 — scripts/benchmark_recall.py

Placeholder for the Phase 5 NDCG benchmark (voyage-context-3 vs voyage-3-large
on laws_regulations, ship-gate ≥3 NDCG points to keep voyage-context-3). For
Phase 1D, just prints:

  "Recall@10 and NDCG@10 benchmark — Phase 5 ship-gate work.
   Owner: Josh. Curated 100-query legal eval set required.
   See docs/tyndale-spec/02_developer_spec.html §7 for the ship-gate spec."

STEP 14 — Verify

  cd runtime
  docker compose up -d qdrant
  uv run python scripts/init_collections.py
  uv run python scripts/seed_fixtures.py

Then test a search end-to-end:
  uv run python -c "
  import asyncio
  from app.knowledge.search import search
  async def go():
      hits = await search('laws_regulations', 'ERISA appeal deadline',
                          effective_date='2026-01-01')
      print(f'Got {len(hits)} hits')
      for h in hits[:3]:
          print(h.payload.get('section'), h.score)
  asyncio.run(go())
  "

Expected: 3+ hits returned with reasonable relevance.

Also verify the effective-date filter enforcement:
  uv run python -c "
  import asyncio
  from app.knowledge.search import search
  async def go():
      try:
          await search('laws_regulations', 'ERISA')   # no effective_date
      except ValueError as e:
          print(f'Correctly blocked: {e}')
  asyncio.run(go())
  "

Expected: prints "Correctly blocked: effective_date filter required for this
collection".

STEP 15 — Single commit

  git add runtime/ intelligence-layer/collections/
  git commit -m "feat(knowledge): Phase 1D — Qdrant local, 4 collections, fixtures seeded"

DO NOT push. Show the commit and the search-test output.

STEP 16 — REPORT BACK

In your reply, include:
- `git log --oneline -2`
- `git diff --stat HEAD~1`
- Output of init_collections.py (created vs already-exists per collection)
- Output of seed_fixtures.py (records loaded per collection)
- Output of the two search tests (hits + blocked-query)
- Any deviation from this prompt and why
- Anything that needs my attention (especially: did the fixture data feel
  realistic enough? are the JSON Schemas tight enough for Josh to extend
  in Phase 5?)

DO NOT proceed beyond this prompt. Phase 5 work — production ingestion of real
data (AMA CPT, CMS NCCI/MUE, eCFR, payer policies), the NDCG benchmark, the
Azure VPC Qdrant deployment, the Presidio benchmark — picks up from this
foundation when Brock has the AMA CPT license and Azure tenancy is ready.

END — Phase 1D Prompt
```

---

## What this delivers

After Phase 1D executes and is pushed:

- Local Qdrant running via Docker Compose alongside the FastAPI runtime + Postgres
- Four collections initialized with the locked metadata schemas from build kit Task 23
- Voyage AI embedding client wired (with model-per-collection mapping per the developer spec)
- Voyage rerank-2.5 client wired (per-collection default instructions loaded; query-level overrides in Phase 2)
- Hybrid search (vector + BM25 with RRF) operational on all four collections
- **Mandatory effective-date filter enforced for `laws_regulations` and `payer_policies`** — both in the search wrapper and in the PreToolUse hook (Phase 1C stub). Defense in depth.
- Fixtures from build kit Task 25 seeded (~80 records total across the four collections) so the runtime has real query targets from day one
- JSON Schemas for each collection so Josh can extend without re-deriving them
- Default rerank instructions per collection captured for Phase 2 subagent use

## What's deferred to later phases

- **Production ingestion** (real AMA CPT, CMS NCCI/MUE, eCFR + state law, payer medical-necessity policies) → Phase 5 (Josh) — blocked on AMA CPT license
- **NDCG@10 benchmark** (voyage-context-3 vs voyage-3-large on `laws_regulations`, ship-gate ≥3 NDCG points to keep voyage-context-3) → Phase 5 (Josh)
- **Azure VPC Qdrant deployment** (self-hosted on Azure Container Apps with no public ingress, daily snapshots to Azure Blob, twice-yearly restore drills) → Phase 5, blocked on Azure tenancy
- **Presidio scrubbing benchmark** on hand-labeled bills/EOBs → Phase 4, owner: security/HIPAA contact
- **Recall@10 ≥ 0.95 and p95 latency < 50ms ship gates** → Phase 5
- **NCCI and MUE structured Postgres tables** (loaded separately from Qdrant; only narrative goes in `error_detection_rules`) → Phase 5
- **Regulation Researcher cron** (weekly eCFR diffs, NCCI quarterly drops, state DOI updates) → Phase 5
- **Per-collection rerank instruction tuning** → Phase 5 with real production query distributions

## Now you have the full Phase 1 set

The four Phase 1 prompts together (1A, 1B, 1C, 1D) cover the foundations track. After all four are landed, Phase 2 wires the real intelligence: Lead Planner orchestration through Bill Detective + Math Person, Document Intelligence OCR on real bills, end-to-end MRI scenario running, dashboard binding to real data, encounter verification UI, and the start of the feedback-loop capture surface.
