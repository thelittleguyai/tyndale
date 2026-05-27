"""Idempotent: ensure all four collections exist with their locked schemas.

Usage: uv run python scripts/init_collections.py
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/

from app.knowledge.client import ensure_collection  # noqa: E402
from app.knowledge.collections import COLLECTIONS  # noqa: E402


async def main() -> None:
    for name, cfg in COLLECTIONS.items():
        created = await ensure_collection(
            name,
            vector_size=cfg.vector_size,
            distance=cfg.distance,
            hybrid_enabled=cfg.hybrid_enabled,
            quantization=cfg.quantization,
        )
        print(f"{'created' if created else 'already-exists':>15}: {name}")


if __name__ == "__main__":
    asyncio.run(main())
