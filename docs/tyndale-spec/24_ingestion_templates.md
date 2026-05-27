# Task 24 — Build the ingestion script templates

**Phase:** 5 · Knowledge collection scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** Task 23

> **DATA-SOURCING & LICENSING REALITY (read before building ingestion).**
> The reference data has two real costs and a lot of free-but-laborious
> acquisition. Plan licensing conversations EARLY — they're long-lead-time
> and affect unit economics. Verify all current terms directly; the notes
> below are directional, not quotes.
>
> - **Federal & state laws (`laws_regulations`):** mostly FREE. Federal
>   statutes/regulations are public domain (eCFR, govinfo.gov, Cornell
>   LII). State laws are scattered across 50 state sites — laborious but
>   free. The Regulation Researcher cron keeps it current.
> - **NCCI / MUE bill-error intelligence (`error_detection_rules`):** FREE
>   from CMS, quarterly. The highest-value error-detection data you have.
> - **Billing codes (`billing_codes`):** ICD-10 and HCPCS are FREE from
>   CMS. **CPT codes are AMA-owned and require a PAID commercial license.**
>   This is not optional and not free — budget for it and factor it into
>   COGS. Start the AMA conversation early.
> - **Payer policies (`payer_policies`):** CMS LCDs/NCDs and the Medicare
>   Coverage Database are FREE. Commercial payer medical-necessity policies
>   are published publicly by payers but scattered and inconsistent — check
>   terms-of-use before systematic ingestion, and START NARROW (biggest
>   payers in your launch geography only).
> - **Pricing (`cost_estimation` data):** Medicare fee schedules / RVUs are
>   FREE (good benchmark). **FAIR Health UCR is a PAID commercial license**
>   (the gold standard for "fair commercial price"). Hospital price-
>   transparency machine-readable files are free but enormous and messy.
>   V1-Lite can start with the free Medicare benchmark + the 3-digit-ZIP
>   FAIR Health fallback, and add richer pricing later.
>
> Two real licensing costs to plan for: **AMA CPT** and **FAIR Health.**
> This data layer is shared by V1-Lite and full Tyndale (mode: universal),
> so none of it is throwaway, and it can be acquired in parallel with the
> rest of the build regardless of which input method (upload or FHIR) is
> live.

## What this task does

Creates Python script templates for ingesting source data into each Qdrant collection. The templates are scaffolding — engineers fill in source-specific extraction logic. The chunking strategy, embedding model selection, and metadata mapping are all in the template.

## Prompt to paste into Claude Code

```
Create Python script templates in `collections/ingestion/`:

1. `ingest_billing_codes.py`
2. `ingest_error_detection_rules.py`
3. `ingest_laws_regulations.py`
4. `ingest_payer_policies.py`

Plus a shared module:
5. `common.py` — embedding clients, Qdrant client setup, common utilities

Each ingestion script should follow this structure:

```python
"""
Ingestion script for the {collection_name} Qdrant collection.

USAGE:
    python ingest_{collection_name}.py --source <path> [--dry-run]

This script is a TEMPLATE. The engineering team fills in the
source-specific extraction logic (marked with TODO comments).

Owned by: <Josh / engineering team>
Last reviewed: <date>
"""

import argparse
from pathlib import Path
from common import (
    get_qdrant_client,
    get_embedding_client,
    chunk_text,
    validate_metadata,
)

COLLECTION_NAME = "{collection_name}"
EMBEDDING_MODEL = "{voyage-3-large OR voyage-context-3}"  # per spec
EMBEDDING_DIM = 1024
EMBEDDING_PRECISION = "int8"

def extract_records_from_source(source_path: Path) -> list[dict]:
    """
    TODO: implement source-specific extraction logic.

    Source format: <describe source format>
    Output: list of dicts matching the collection's metadata schema.
    """
    raise NotImplementedError("Engineering team to implement")


def chunk_record(record: dict) -> list[dict]:
    """
    Chunk a single record according to the collection's chunking strategy.

    {Collection-specific chunking strategy goes here.}
    """
    # TODO: implement per spec
    raise NotImplementedError


def embed_chunk(chunk_text: str) -> list[float]:
    """Generate embedding for a chunk."""
    client = get_embedding_client(EMBEDDING_MODEL)
    return client.embed(chunk_text)


def upsert_chunks(chunks: list[dict], dry_run: bool = False):
    """Upsert chunks to Qdrant collection."""
    qclient = get_qdrant_client()
    for chunk in chunks:
        validate_metadata(chunk, COLLECTION_NAME)
        if not dry_run:
            embedding = embed_chunk(chunk["chunk_text"])
            qclient.upsert(
                collection_name=COLLECTION_NAME,
                points=[{
                    "id": chunk["chunk_id"],
                    "vector": embedding,
                    "payload": chunk,
                }],
            )
        else:
            print(f"DRY RUN: would upsert {chunk['chunk_id']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Extracting records from {args.source}...")
    records = extract_records_from_source(args.source)
    print(f"Extracted {len(records)} records.")

    print("Chunking records...")
    chunks = []
    for record in records:
        chunks.extend(chunk_record(record))
    print(f"Generated {len(chunks)} chunks.")

    print("Upserting to Qdrant...")
    upsert_chunks(chunks, dry_run=args.dry_run)
    print("Done.")


if __name__ == "__main__":
    main()
```

For each collection, fill in:
- COLLECTION_NAME
- EMBEDDING_MODEL (voyage-context-3 for laws_regulations; voyage-3-large for others)
- The chunking strategy in the chunk_record docstring (per Decision 8):
  * billing_codes: one chunk per code (100-300 tok)
  * error_detection_rules: 200-500 tok per chunk; structured rules in
    Postgres, only narrative goes to Qdrant
  * laws_regulations: one chunk per statute/regulation section (800-1500
    tok); parent Title/Part/Subpart heading inline at chunk top
  * payer_policies: one chunk per policy section (500-1000 tok)
- A comment describing the expected source format (e.g., CSV with
  columns X, Y, Z; or PDF requiring OCR; or HTML scrape)

For common.py:

```python
"""
Shared utilities for ingestion scripts.

This is scaffolding — engineering team adds the actual client setup
and Qdrant connection details.
"""

import os
from typing import Optional

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")


def get_qdrant_client():
    """TODO: return configured Qdrant client."""
    raise NotImplementedError


def get_embedding_client(model: str):
    """TODO: return configured Voyage embedding client for the specified model."""
    raise NotImplementedError


def chunk_text(text: str, target_tokens: int, overlap: int = 0) -> list[str]:
    """
    Chunk text by target token count, respecting natural boundaries.

    TODO: implement using tiktoken or similar tokenizer.
    """
    raise NotImplementedError


def validate_metadata(chunk: dict, collection_name: str) -> bool:
    """
    Validate chunk metadata against the collection's JSON schema.
    Raises ValueError if invalid.

    TODO: implement using the JSON Schema from collections/schemas/.
    """
    raise NotImplementedError
```

After creating all files, also add `collections/ingestion/README.md`:

```markdown
# Ingestion Scripts

Templates for ingesting source data into Tyndale's 4 Qdrant collections.

## Status

These are SCAFFOLDS. The engineering team fills in:
- `extract_records_from_source()` per collection (source-specific logic)
- `common.py` client implementations
- Tokenizer choice for `chunk_text()`

## Order of operations for V1

1. Engineering implements common.py clients
2. Engineering implements per-collection extract_records_from_source
3. Run with --dry-run first
4. Run for real on small batch, validate
5. Run full ingestion in maintenance window

## Source data references

- billing_codes: CMS CPT/HCPCS/ICD-10 quarterly releases
- error_detection_rules: CMS NCCI/MUE quarterly + payer policy docs
- laws_regulations: eCFR feeds + state legislative databases
- payer_policies: payer medical-necessity policy publications
```

Commit with message "Add ingestion script templates".
```

## Done when

- 4 Python ingestion templates + common.py + README exist in `collections/ingestion/`
- Each script has the structured template with TODOs marked
- Git log shows the commit

## Next task

[Task 25 — Build the test fixtures](25_test_fixtures.md)
