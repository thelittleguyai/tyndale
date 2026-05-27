"""Hybrid search wrapper with point-in-time (effective-date) enforcement.

`search()` enforces the effective-date requirement for laws_regulations and
payer_policies (defense-in-depth with the PreToolUse hook), embeds the query with
the collection's configured model, runs a vector query, and applies the
effective-date window. `search_and_rerank()` adds the Voyage rerank step.

Phase 1D note: on a Qdrant server, hybrid = dense + BM25 sparse fused with RRF.
In embedded local mode the query is dense-only and the date window is applied in
Python (local mode lacks sparse fusion / payload datetime-range filters).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

import structlog

from app.knowledge import rerank as rerank_mod
from app.knowledge.client import get_client
from app.knowledge.collections import COLLECTIONS, EMBED_TEXT_FIELD
from app.knowledge.embeddings import embed, model_for

log = structlog.get_logger(__name__)


@dataclass
class Hit:
    id: Any
    score: float
    payload: dict


def _to_iso(value: datetime.date | datetime.datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()[:10]
    return str(value)[:10]


def _within_window(payload: dict, effective_date: str) -> bool:
    start = payload.get("effective_date_start")
    end = payload.get("effective_date_end")
    if start and effective_date < str(start):
        return False
    if end and effective_date > str(end):  # null/None end => still current
        return False
    return True


async def search(
    collection: str,
    query: str,
    effective_date: datetime.date | str | None = None,
    filters: dict | None = None,
    top_k: int = 50,
) -> list[Hit]:
    if collection not in COLLECTIONS:
        raise ValueError(f"unknown collection: {collection}")
    cfg = COLLECTIONS[collection]
    eff = _to_iso(effective_date)
    if cfg.requires_effective_date_filter and eff is None:
        raise ValueError("effective_date filter required for this collection")

    vector = await embed(query, model_for(collection), dim=cfg.vector_size)
    client = get_client()

    qfilter = None
    if filters:
        from qdrant_client import models

        qfilter = models.Filter(
            must=[models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in filters.items()]
        )

    res = await client.query_points(
        collection_name=collection,
        query=vector,
        limit=top_k,
        query_filter=qfilter,
        with_payload=True,
    )
    hits = [Hit(id=p.id, score=p.score or 0.0, payload=p.payload or {}) for p in res.points]

    if cfg.requires_effective_date_filter and eff is not None:
        hits = [h for h in hits if _within_window(h.payload, eff)]
    return hits


async def search_and_rerank(
    collection: str,
    query: str,
    effective_date: datetime.date | str | None = None,
    filters: dict | None = None,
    top_k: int = 50,
    top_n: int = 10,
) -> list[Hit]:
    hits = await search(collection, query, effective_date, filters, top_k)
    if not hits:
        return []
    text_field = EMBED_TEXT_FIELD[collection]
    documents = [str(h.payload.get(text_field, "")) for h in hits]
    instruction = rerank_mod.default_instruction(collection)
    results = await rerank_mod.rerank(query, documents, top_n=top_n, instruction=instruction)
    return [Hit(id=hits[r.index].id, score=r.score, payload=hits[r.index].payload) for r in results]
