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
import time

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
_MAX_TOTAL_BACKOFF_S = 45.0  # never hold a tool call for minutes waiting on quota

# Client-side discipline (e2e 2026-09-23 B1): dev spent days at 429 on /v1/embeddings. A
# per-process token bucket keeps a burst of parallel tool calls under the account's
# per-minute quota, a small concurrency cap keeps retries from stampeding, and a short-TTL
# cache answers the SAME query again without a call — an audit asks about the same codes
# repeatedly (the Bill Detective and the Math Person both look up the bill's CPTs).
_RPM_LIMIT = 300
_MAX_CONCURRENCY = 4
_QUERY_CACHE_TTL_S = 15 * 60
_QUERY_CACHE_MAX = 512


class EmbeddingUnavailable(RuntimeError):
    """Voyage could not embed (quota exhausted after backoff, or a non-retryable failure).
    Raised as one typed error so the knowledge tools record it as ONE retrieval failure."""


class _TokenBucket:
    """``rpm`` permits per minute, refilled continuously; ``acquire`` waits, never drops."""

    def __init__(self, rpm: int) -> None:
        self.rate = rpm / 60.0
        self.capacity = float(max(1, rpm // 10))  # a modest burst, not the whole minute
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self._lock: asyncio.Lock | None = None

    def _lock_for_loop(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self) -> float:
        """Returns the seconds waited (for the log line)."""
        waited = 0.0
        async with self._lock_for_loop():
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return waited
                need = (1.0 - self.tokens) / self.rate
                waited += need
                await asyncio.sleep(need)


_bucket = _TokenBucket(_RPM_LIMIT)
_semaphore: asyncio.Semaphore | None = None


def _sem() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _semaphore


# (model, dim, input_type, text) -> (expires_at, vector)
_query_cache: dict[tuple[str, int, str, str], tuple[float, list[float]]] = {}


def _cache_get(key: tuple[str, int, str, str]) -> list[float] | None:
    hit = _query_cache.get(key)
    if hit is None:
        return None
    if hit[0] < time.monotonic():
        _query_cache.pop(key, None)
        return None
    return hit[1]


def _cache_put(key: tuple[str, int, str, str], vec: list[float]) -> None:
    if len(_query_cache) >= _QUERY_CACHE_MAX:
        # drop the oldest entries (insertion order) rather than growing without bound
        for k in list(_query_cache)[: _QUERY_CACHE_MAX // 4]:
            _query_cache.pop(k, None)
    _query_cache[key] = (time.monotonic() + _QUERY_CACHE_TTL_S, vec)


def cache_clear() -> None:
    """Tests only."""
    _query_cache.clear()

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
    """POST to a Voyage endpoint under the per-process limiter, with shared retry/backoff
    (429 + 5xx, honoring Retry-After, capped in total). Returns the parsed JSON, or raises
    ``EmbeddingUnavailable`` — never a bare HTTP error into a tool result."""
    from app.knowledge import health

    settings = get_settings()
    endpoint = url.rsplit("/", 1)[-1]
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }
    total_backoff = 0.0
    async with _sem():
        waited = await _bucket.acquire()
        if waited > 0.5:
            log.info("voyage.throttled", endpoint=endpoint, waited_s=round(waited, 2))
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for attempt in range(_MAX_EMBED_RETRIES):
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_EMBED_RETRIES - 1:
                        ra = resp.headers.get("retry-after", "")
                        delay = float(ra) if ra.replace(".", "", 1).isdigit() else min(2.0**attempt, 30.0)
                        health.record_voyage(
                            endpoint, False, status=resp.status_code, error=_body(resp)[:200]
                        )
                        if total_backoff >= _MAX_TOTAL_BACKOFF_S:
                            break  # backoff budget spent — fall through to the final verdict
                        delay = min(delay, _MAX_TOTAL_BACKOFF_S - total_backoff)
                        total_backoff += delay
                        log.warning(
                            "voyage.retry", endpoint=endpoint, status=resp.status_code,
                            attempt=attempt + 1, delay=delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    if resp.status_code >= 400:
                        detail = _body(resp)[:300]
                        log.warning(
                            "voyage.embed_failed", endpoint=endpoint, status=resp.status_code,
                            detail=detail, n_inputs=_n_inputs(payload),
                        )
                        health.record_voyage(endpoint, False, status=resp.status_code, error=detail)
                        raise EmbeddingUnavailable(f"voyage {endpoint} {resp.status_code}: {detail}")
                    health.record_voyage(endpoint, True, status=resp.status_code)
                    return resp.json()
        except EmbeddingUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — transport/timeout: one typed failure
            log.warning("voyage.embed_failed", endpoint=endpoint, status=None, detail=str(exc)[:300])
            health.record_voyage(endpoint, False, status=None, error=str(exc))
            raise EmbeddingUnavailable(str(exc)) from exc
    # only reachable when the backoff budget ran out on a retryable status
    detail = f"gave up after {total_backoff:.0f}s of backoff (last status {resp.status_code})"
    log.warning("voyage.embed_failed", endpoint=endpoint, status=resp.status_code, detail=detail)
    raise EmbeddingUnavailable(f"voyage {endpoint}: {detail}")


def _body(resp: object) -> str:
    text = getattr(resp, "text", "")
    return text if isinstance(text, str) else ""


def _n_inputs(payload: dict) -> int:
    if isinstance(payload.get("input"), list):
        return len(payload["input"])
    if isinstance(payload.get("inputs"), list):
        return sum(len(g) for g in payload["inputs"] if isinstance(g, list))
    return 1


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
    """Embed a single QUERY. A query against a contextualized collection is embedded as a
    one-chunk group with input_type='query' — which MUST match the model the stored
    documents used (DL-74). Answered from the short-TTL cache when the same query was
    embedded recently."""
    return (await embed_queries([text], model, dim))[0]


async def embed_queries(texts: list[str], model: str, dim: int = 1024) -> list[list[float]]:
    """Embed several queries in ONE Voyage call (the misses, after the cache and after
    de-duplication) — the batching seam for a tool that issues several queries at once."""
    out: list[list[float] | None] = [None] * len(texts)
    misses: dict[str, list[int]] = {}
    live = bool(get_settings().voyage_api_key)
    for i, text in enumerate(texts):
        cached = _cache_get((model, dim, "query", text)) if live else None
        if cached is not None:
            out[i] = cached
        else:
            misses.setdefault(text, []).append(i)
    if misses:
        unique = list(misses)
        if is_contextualized(model):
            nested = await embed_contextualized([[t] for t in unique], model, input_type="query", dim=dim)
            vectors = [group[0] for group in nested]
        else:
            vectors = await embed_batch(unique, model, dim, input_type="query")
        live = bool(get_settings().voyage_api_key)  # the stub is free and deterministic: no cache
        for text, vec in zip(unique, vectors, strict=True):
            if live:
                _cache_put((model, dim, "query", text), vec)
            for i in misses[text]:
                out[i] = vec
    return [v for v in out if v is not None]
