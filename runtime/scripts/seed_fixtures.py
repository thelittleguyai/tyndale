"""Load fixtures from intelligence-layer/collections/fixtures into Qdrant.

Validates each record against the matching JSON Schema, embeds the collection's
text field, and upserts with the record as payload. Skips invalid records with a
clear message.

Usage: uv run python scripts/seed_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/

from jsonschema import Draft7Validator  # noqa: E402
from qdrant_client import models  # noqa: E402

from app.knowledge.client import get_client  # noqa: E402
from app.knowledge.collections import COLLECTIONS, EMBED_TEXT_FIELD, ID_FIELD  # noqa: E402
from app.knowledge.embeddings import (  # noqa: E402
    embed_batch,
    embed_grouped,
    is_contextualized,
    model_for,
)

# Resolve the intelligence-layer root the way app.agents.context_loader does:
# TYNDALE_INTELLIGENCE_LAYER_ROOT (set to /app/intelligence-layer in the deployed
# image) wins; otherwise fall back to the repo layout (runtime/scripts -> repo root).
# Without this, an in-image run resolves parents[2] to "/" and can't find fixtures.
_IL_ROOT = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_IL_DIR = pathlib.Path(_IL_ROOT) if _IL_ROOT else REPO_ROOT / "intelligence-layer"
COLLECTIONS_DIR = _IL_DIR / "collections"
_NS = uuid.UUID("9f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d")


def _load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _records(raw) -> list[dict]:
    # Fixtures are objects with {_meta, records:[...]}; tolerate a bare array too.
    if isinstance(raw, dict):
        return raw.get("records", [])
    return [r for r in raw if isinstance(r, dict) and "_meta" not in r]


def _parent_key(rec: dict) -> tuple:
    """Group key for contextualized seeding — the parent authority a chunk belongs
    to (laws_regulations: statute + parent_part). Falls back to the chunk's own id
    (its own group) when no parent fields are present."""
    statute, part = rec.get("statute"), rec.get("parent_part")
    if statute and part:
        return (str(statute), str(part))
    return (str(rec.get("chunk_id") or id(rec)),)


async def _embed_records_grouped(records: list[dict], name: str, model: str, dim: int) -> list:
    """Embed records grouped by parent authority (contextualized models), returning
    per-record vectors in ``records`` order so the caller can zip them with records."""
    text_field = EMBED_TEXT_FIELD[name]
    buckets: dict[tuple, list[tuple[int, str]]] = {}
    for i, rec in enumerate(records):
        buckets.setdefault(_parent_key(rec), []).append((i, str(rec.get(text_field, ""))))
    keys = list(buckets)
    groups = [[text for _, text in buckets[k]] for k in keys]
    nested = await embed_grouped(groups, model, dim, input_type="document")
    vectors: list = [None] * len(records)
    for key, group_vecs in zip(keys, nested):
        for (orig_i, _), vec in zip(buckets[key], group_vecs):
            vectors[orig_i] = vec
    return vectors


async def seed_one(name: str) -> tuple[int, int]:
    schema = _load(COLLECTIONS_DIR / "schemas" / f"{name}.json")
    validator = Draft7Validator(schema)
    records = _records(_load(COLLECTIONS_DIR / "fixtures" / f"{name}.json"))

    valid: list[dict] = []
    skipped = 0
    for rec in records:
        errors = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
        if errors:
            key = rec.get(ID_FIELD[name], "<?>")
            print(f"  SKIP {name}[{key}]: {errors[0].message}")
            skipped += 1
            continue
        valid.append(rec)

    if not valid:
        print(f"{'seeded':>15}: {name} — 0 records (skipped {skipped})")
        return 0, skipped

    model = model_for(name)
    dim = COLLECTIONS[name].vector_size
    try:
        # Contextualized models (voyage-context-3 for laws_regulations, CO-13) embed
        # stored chunks grouped by parent authority (input_type="document"); flat
        # models embed each text independently.
        if is_contextualized(model):
            vectors = await _embed_records_grouped(valid, name, model, dim)
        else:
            texts = [str(r.get(EMBED_TEXT_FIELD[name], "")) for r in valid]
            vectors = await embed_batch(texts, model, dim)
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(_NS, f"{name}:{rec.get(ID_FIELD[name])}")),
                vector=vec,
                payload=rec,
            )
            for rec, vec in zip(valid, vectors)
        ]
        await get_client().upsert(collection_name=name, points=points)
    except Exception as exc:  # noqa: BLE001 — one collection's failure must not abort the rest
        # e.g. a Voyage 429 that outlived its retries, or a transient endpoint error.
        print(f"{'FAILED':>15}: {name} — skipped ({type(exc).__name__}: {str(exc)[:200]})")
        return 0, skipped
    print(f"{'seeded':>15}: {name} — {len(points)} records (skipped {skipped})")
    return len(points), skipped


async def main() -> None:
    total = 0
    incomplete: list[str] = []
    for name in COLLECTIONS:
        loaded, _ = await seed_one(name)
        total += loaded
        if loaded == 0:
            incomplete.append(name)
    ok = len(COLLECTIONS) - len(incomplete)
    print(f"{'TOTAL':>15}: {total} records across {ok}/{len(COLLECTIONS)} collections")
    if incomplete:
        print(f"{'INCOMPLETE':>15}: {', '.join(incomplete)} (see errors above)")
    # Partial success is fine (grounds what we can); only a total wipeout fails the job.
    if total == 0:
        raise SystemExit("seed failed: no records seeded across any collection")


if __name__ == "__main__":
    asyncio.run(main())
