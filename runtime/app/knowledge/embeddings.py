"""Voyage AI embedding client.

When VOYAGE_API_KEY is set, calls the Voyage embeddings API. When it is unset
(Phase 1C/1D default), returns a DETERMINISTIC stub vector so local seeding and
search run end-to-end without a key or network. The stub is not semantically
meaningful — real relevance requires Voyage (Phase 2+).
"""

from __future__ import annotations

import hashlib
import math
import random

import httpx
import structlog

from app.config import get_settings
from app.knowledge.collections import COLLECTIONS

log = structlog.get_logger(__name__)

VOYAGE_EMBED_URL = "https://api.voyageai.com/v1/embeddings"

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
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(VOYAGE_EMBED_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return [item["embedding"] for item in data["data"]]


async def embed(text: str, model: str, dim: int = 1024) -> list[float]:
    return (await embed_batch([text], model, dim))[0]
