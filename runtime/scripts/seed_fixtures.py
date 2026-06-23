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
from app.knowledge.embeddings import embed_batch, model_for  # noqa: E402

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

    texts = [str(r.get(EMBED_TEXT_FIELD[name], "")) for r in valid]
    try:
        vectors = await embed_batch(texts, model_for(name), dim=COLLECTIONS[name].vector_size)
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
        # e.g. laws_regulations uses voyage-context-3, which embed_batch doesn't
        # support yet (Phase 5) -> 400; or a Voyage 429 that outlived its retries.
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
