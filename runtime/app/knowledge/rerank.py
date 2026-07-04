"""Voyage rerank-2.5 client.

When VOYAGE_API_KEY is set, calls the Voyage rerank API. When unset, a stub ranks
documents by lexical overlap with the query (enough signal for local dev).
Per-collection default instructions are loaded from the intelligence-layer.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

VOYAGE_RERANK_URL = "https://api.voyageai.com/v1/rerank"
RERANK_MODEL = "rerank-2.5"


def _intelligence_layer_root() -> Path:
    # Honor the TYNDALE_INTELLIGENCE_LAYER_ROOT override (container layouts + tests),
    # matching app/agents/context_loader.py; else derive from this file's location
    # (runtime/app/knowledge/rerank.py -> repo_root/intelligence-layer).
    override = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "intelligence-layer"


@dataclass
class RerankResult:
    index: int
    document: str
    score: float


@lru_cache(maxsize=1)
def _instructions() -> dict[str, str]:
    """Parse the per-collection rerank instructions. Cached; call
    ``_instructions.cache_clear()`` in tests that repoint the layer root."""
    path = _intelligence_layer_root() / "collections" / "rerank_instructions.md"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for match in re.finditer(
        r"^##\s+(\S+)\s*\n+(.+?)(?=\n##\s|\Z)", text, re.DOTALL | re.MULTILINE
    ):
        name = match.group(1).strip()
        body = match.group(2).strip().strip('"').strip()
        out[name] = body
    return out


def default_instruction(collection: str) -> str | None:
    return _instructions().get(collection)


async def rerank(
    query: str,
    documents: list[str],
    top_n: int = 10,
    instruction: str | None = None,
) -> list[RerankResult]:
    settings = get_settings()
    if not settings.voyage_api_key:
        # Stub: lexical-overlap score (no network/key needed).
        q_tokens = set(re.findall(r"\w+", query.lower()))
        scored = []
        for i, doc in enumerate(documents):
            d_tokens = set(re.findall(r"\w+", doc.lower()))
            overlap = len(q_tokens & d_tokens) / (len(q_tokens) or 1)
            scored.append(RerankResult(index=i, document=doc, score=overlap))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_n]

    payload: dict = {"query": query, "documents": documents, "model": RERANK_MODEL, "top_k": top_n}
    if instruction:
        payload["instruction"] = instruction
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(VOYAGE_RERANK_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return [
        RerankResult(
            index=item["index"], document=documents[item["index"]], score=item["relevance_score"]
        )
        for item in data["data"]
    ]
