"""Load fixtures from intelligence-layer/collections/fixtures into Qdrant.

Validates each record against the matching JSON Schema, embeds the collection's
text field, and upserts with the record as payload. Skips invalid records with a
clear message.

Usage: uv run python scripts/seed_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/

from jsonschema import Draft7Validator  # noqa: E402
from qdrant_client import models  # noqa: E402

from app.knowledge.client import get_client  # noqa: E402
from app.knowledge.collections import COLLECTIONS, EMBED_TEXT_FIELD, ID_FIELD  # noqa: E402
from app.knowledge.embeddings import embed_batch, model_for  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COLLECTIONS_DIR = REPO_ROOT / "intelligence-layer" / "collections"
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
    print(f"{'seeded':>15}: {name} — {len(points)} records (skipped {skipped})")
    return len(points), skipped


async def main() -> None:
    total = 0
    for name in COLLECTIONS:
        loaded, _ = await seed_one(name)
        total += loaded
    print(f"{'TOTAL':>15}: {total} records seeded across {len(COLLECTIONS)} collections")


if __name__ == "__main__":
    asyncio.run(main())
