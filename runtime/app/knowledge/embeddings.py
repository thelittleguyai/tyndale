"""Voyage AI embedding client.

When VOYAGE_API_KEY is set, calls Voyage via one of two endpoints:
  * /v1/embeddings — flat text embeddings (voyage-3-large: billing_codes,
    error_detection_rules, payer_policies).
  * /v1/contextualizedembeddings — contextualized chunk embeddings
    (voyage-context-3: laws_regulations, per collections.py / spec §7). Chunks are
    grouped by parent authority and embedded aware of their neighbors. Queries and
    stored chunks MUST use the matching model + input_type ("query" vs "document")
    or retrieval silently degrades (DL-74). Switching a collection's model/endpoint
    requires re-seeding — vectors from different endpoints aren't cross-comparable.

When VOYAGE_API_KEY is unset (local/CI default), returns DETERMINISTIC stub vectors
in the same shapes so seeding/search run end-to-end without a key. The stub is not
semantically meaningful — real relevance requires Voyage.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random

import httpx
import structlog

from app.config import get_settings
from app.knowledge.collections import COLLECTIONS

log = structlog.get_logger(__name__)

VOYAGE_EMBED_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_CONTEXT_EMBED_URL = "https://api.voyageai.com/v1/contextualizedembeddings"

# Retry transient Voyage failures (rate limits + 5xx) with exponential backoff so a
# burst of seed/search batches doesn't fail the whole run on a 429. Shared by both
# endpoints via _post_voyage.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_EMBED_RETRIES = 5

# collection -> Settings attribute holding the (env-overridable) model name
_ENV_MODEL_ATTR = {
    "billing_codes": "embedding_model_billing_codes",
    "error_detection_rules": "embedding_model_error_detection",
    "laws_regulations": "embedding_model_laws",
    "payer_policies": "embedding_model_payer_policies",
}


def model_for(collection: str) -> str:
    settings = get_settings()
    attr = _ENV_MODEL_ATTR.get(collection)
    return getattr(settings, attr) if attr else COLLECTIONS[collection].embedding_model


def is_contextualized(model: str) -> bool:
    """True for Voyage contextualized-chunk models (voyage-context-*), which use the
    /v1/contextualizedembeddings endpoint (grouped inputs + input_type)."""
    return model.startswith("voyage-context-")


def _stub_vector(text: str, dim: int = 1024) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def _post_voyage(url: str, payload: dict) -> dict:
    """POST to a Voyage endpoint with shared retry/backoff (429 + 5xx, honoring
    Retry-After). Returns the parsed JSON. Used by BOTH embedding endpoints."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(_MAX_EMBED_RETRIES):
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_EMBED_RETRIES - 1:
                ra = resp.headers.get("retry-after", "")
                delay = float(ra) if ra.replace(".", "", 1).isdigit() else min(2.0**attempt, 30.0)
                log.warning(
                    "voyage.retry", status=resp.status_code, attempt=attempt + 1, delay=delay
                )
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
    raise RuntimeError("unreachable: voyage retry loop exited without return/raise")


async def embed_contextualized(
    groups: list[list[str]],
    model: str,
    input_type: str = "document",
    dim: int = 1024,
) -> list[list[list[float]]]:
    """Embed grouped chunks via the contextualized endpoint. ``groups`` is a list of
    documents, each a list of chunk strings; returns the same nested shape of vectors
    (group -> chunk -> vector), order preserved. Stub (no key) returns correctly
    nested stub vectors."""
    settings = get_settings()
    if not settings.voyage_api_key:
        return [[_stub_vector(chunk, dim) for chunk in group] for group in groups]
    data = await _post_voyage(
        VOYAGE_CONTEXT_EMBED_URL,
        {
            "inputs": groups,
            "model": model,
            "input_type": input_type,
            "output_dimension": dim,
            "output_dtype": "float",
        },
    )
    # Response: data[g]["data"][c]["embedding"] (+ index fields). Sort by index to
    # preserve group->chunk ordering regardless of return order.
    out: list[list[list[float]]] = []
    for group in sorted(data["data"], key=lambda g: g.get("index", 0)):
        chunks = sorted(group["data"], key=lambda c: c.get("index", 0))
        out.append([c["embedding"] for c in chunks])
    return out


async def embed_batch(
    texts: list[str], model: str, dim: int = 1024, input_type: str = "document"
) -> list[list[float]]:
    """Embed a flat list of texts. voyage-3-large -> /v1/embeddings (unchanged). A
    contextualized model has no grouping in a flat batch, so each text becomes its
    own single-chunk group (correct, but embed_grouped() — grouping by parent
    authority — gives the full context benefit)."""
    settings = get_settings()
    if not settings.voyage_api_key:
        return [_stub_vector(t, dim) for t in texts]
    if is_contextualized(model):
        log.info(
            "voyage.contextualized_flat_batch",
            note="each text embedded as its own group; embed_grouped() recommended for parent context",
            model=model,
            n=len(texts),
        )
        nested = await embed_contextualized(
            [[t] for t in texts], model, input_type=input_type, dim=dim
        )
        return [group[0] for group in nested]
    data = await _post_voyage(
        VOYAGE_EMBED_URL,
        {"input": texts, "model": model, "output_dimension": dim, "output_dtype": "float"},
    )
    return [item["embedding"] for item in data["data"]]


async def embed_grouped(
    groups: list[list[str]], model: str, dim: int = 1024, input_type: str = "document"
) -> list[list[list[float]]]:
    """Grouping-aware document embedding — the entry point the laws seeding path uses.
    Contextualized models embed each group with neighbor context; non-context models
    embed flat and re-nest to the same shape (so callers are model-agnostic)."""
    if is_contextualized(model):
        return await embed_contextualized(groups, model, input_type=input_type, dim=dim)
    flat = await embed_batch([chunk for group in groups for chunk in group], model, dim)
    out: list[list[list[float]]] = []
    i = 0
    for group in groups:
        out.append(flat[i : i + len(group)])
        i += len(group)
    return out


async def embed(text: str, model: str, dim: int = 1024) -> list[float]:
    """Embed a single text. A query against a contextualized collection is embedded
    as a one-chunk group with input_type='query' — which MUST match the model the
    stored documents used (DL-74)."""
    if is_contextualized(model):
        nested = await embed_contextualized([[text]], model, input_type="query", dim=dim)
        return nested[0][0]
    return (await embed_batch([text], model, dim))[0]
