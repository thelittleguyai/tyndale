"""Voyage rerank-2.5 client.

When VOYAGE_API_KEY is set, calls the Voyage rerank API. When unset, a stub ranks
documents by lexical overlap with the query (enough signal for local dev).
Per-collection default instructions are loaded from the intelligence-layer.

The request contract (e2e 2026-09-23 B1). Every live rerank call had returned 400 since at
least 2026-09-18 — deterministically, on every collection — because the payload carried an
``instruction`` field. Voyage's rerank API has no such parameter and rejects it before auth:

    {"detail": "... Argument 'instruction' is not supported by our API"}

rerank-2.5 DOES follow instructions, but they are given IN the query ("optional instructions
can be appended or prepended to the query", docs.voyageai.com/docs/reranker). So Brock's
per-collection instruction is prepended to the query text, and the body carries only the
documented fields: query, documents, model, top_k. Documented limits are enforced here too
(≤ 1000 documents; empty documents dropped — they carry no signal and the index map keeps the
caller's positions honest).
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
# The documented request body — nothing else is ever sent (the test pins this set).
RERANK_REQUEST_FIELDS = frozenset({"query", "documents", "model", "top_k", "return_documents", "truncation"})
MAX_RERANK_DOCUMENTS = 1000


class RerankUnavailable(RuntimeError):
    """The reranker could not be used. Callers degrade to the unreranked order — a failed
    rerank must never become a failed search."""


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0)


def build_rerank_payload(
    query: str, documents: list[str], top_n: int, instruction: str | None = None
) -> tuple[dict, list[int]]:
    """(body, index_map): the documented Voyage body, and for each position in
    ``body["documents"]`` the caller's original index (empties are dropped, the list is
    capped at the documented maximum)."""
    q = f"{instruction.strip()}\n\n{query}" if instruction and instruction.strip() else query
    kept = [(i, d) for i, d in enumerate(documents) if isinstance(d, str) and d.strip()]
    kept = kept[:MAX_RERANK_DOCUMENTS]
    body = {
        "query": q,
        "documents": [d for _, d in kept],
        "model": RERANK_MODEL,
        "top_k": max(1, min(int(top_n), len(kept))) if kept else 0,
    }
    assert set(body) <= RERANK_REQUEST_FIELDS
    return body, [i for i, _ in kept]


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

    from app.knowledge import health

    body, index_map = build_rerank_payload(query, documents, top_n, instruction)
    if not index_map:
        return []
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with _make_client() as client:
            resp = await client.post(VOYAGE_RERANK_URL, json=body, headers=headers)
        if resp.status_code >= 400:
            # ONE redacted line with the request SHAPE (never the text) and Voyage's own
            # reason — the thing that would have named the bug in a day, not a week.
            detail = resp.text[:300]
            log.warning(
                "voyage.rerank_failed",
                status=resp.status_code,
                detail=detail,
                request_fields=sorted(body),
                n_documents=len(body["documents"]),
                query_chars=len(body["query"]),
                top_k=body["top_k"],
            )
            health.record_voyage("rerank", False, status=resp.status_code, error=detail)
            raise RerankUnavailable(f"voyage rerank {resp.status_code}: {detail}")
        data = resp.json()
    except RerankUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — transport/timeout/JSON: still "unavailable"
        log.warning("voyage.rerank_failed", status=None, detail=str(exc)[:300])
        health.record_voyage("rerank", False, status=None, error=str(exc))
        raise RerankUnavailable(str(exc)) from exc
    health.record_voyage("rerank", True, status=resp.status_code)
    out: list[RerankResult] = []
    for item in data.get("data") or []:
        pos = int(item["index"])
        if 0 <= pos < len(index_map):
            orig = index_map[pos]
            out.append(RerankResult(index=orig, document=documents[orig], score=float(item["relevance_score"])))
    return out
