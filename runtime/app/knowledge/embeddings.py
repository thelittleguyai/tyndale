"""Voyage AI embedding client.

When VOYAGE_API_KEY is set, calls the Voyage embeddings API. When it is unset
(Phase 1C/1D default), returns a DETERMINISTIC stub vector so local seeding and
search run end-to-end without a key or network. The stub is not semantically
meaningful — real relevance requires Voyage (Phase 2+).
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

# Retry transient Voyage failures (rate limits + 5xx) with exponential backoff so
# a burst of seed/search batches doesn't fail the whole run on a 429.
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


def _stub_vector(text: str, dim: int = 1024) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def embed_batch(texts: list[str], model: str, dim: int = 1024) -> list[list[float]]:
    settings = get_settings()
    if not settings.voyage_api_key:
        return [_stub_vector(t, dim) for t in texts]
    # NOTE: voyage-context-3 uses Voyage's contextualized-embeddings endpoint;
    # wire that variant in Phase 5. This path covers voyage-3-large.
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"input": texts, "model": model, "output_dimension": dim, "output_dtype": "float"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(_MAX_EMBED_RETRIES):
            resp = await client.post(VOYAGE_EMBED_URL, json=payload, headers=headers)
            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_EMBED_RETRIES - 1:
                ra = resp.headers.get("retry-after", "")
                delay = float(ra) if ra.replace(".", "", 1).isdigit() else min(2.0**attempt, 30.0)
                log.warning(
                    "voyage.retry", status=resp.status_code, attempt=attempt + 1, delay=delay
                )
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]
    raise RuntimeError("unreachable: embed retry loop exited without return/raise")


async def embed(text: str, model: str, dim: int = 1024) -> list[float]:
    return (await embed_batch([text], model, dim))[0]
