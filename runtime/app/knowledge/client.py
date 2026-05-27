"""Qdrant client wrapper.

`get_client()` returns a singleton AsyncQdrantClient. The mode is chosen from
QDRANT_URL: an http(s):// URL connects to a server (Docker/Azure); any other
value uses qdrant-client's embedded local mode (path on disk, or ":memory:") so
local dev works without Docker.
"""

from __future__ import annotations

import structlog
from qdrant_client import AsyncQdrantClient, models

from app.config import get_settings

log = structlog.get_logger(__name__)

_client: AsyncQdrantClient | None = None


def _is_server(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def is_server_mode() -> bool:
    return _is_server(get_settings().qdrant_url)


def get_client() -> AsyncQdrantClient:
    """Singleton async Qdrant client (server or embedded local mode)."""
    global _client
    if _client is None:
        settings = get_settings()
        url = settings.qdrant_url
        if _is_server(url):
            _client = AsyncQdrantClient(url=url, api_key=settings.qdrant_api_key or None)
            log.info("qdrant.client", mode="server", url=url)
        elif url in (":memory:", ""):
            _client = AsyncQdrantClient(location=":memory:")
            log.warning("qdrant.client", mode="local-memory", note="embedded; dev only")
        else:
            _client = AsyncQdrantClient(path=url)
            log.warning("qdrant.client", mode="local-disk", path=url, note="embedded; dev only")
    return _client


async def ensure_collection(
    name: str,
    vector_size: int,
    distance: models.Distance = models.Distance.COSINE,
    hybrid_enabled: bool = True,
    quantization: str = "int8",
) -> bool:
    """Idempotent create-if-not-exists. Returns True if created, False if it existed.

    int8 quantization and the BM25 sparse vector are server-side features; in
    embedded local mode the collection is created dense-only (logged).
    """
    client = get_client()
    if await client.collection_exists(name):
        return False

    quantization_config = None
    sparse_vectors_config = None
    if is_server_mode():
        if quantization == "int8":
            quantization_config = models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8, always_ram=True
                )
            )
        if hybrid_enabled:
            modifier = getattr(models, "Modifier", None)
            if modifier is not None:
                sparse_vectors_config = {"bm25": models.SparseVectorParams(modifier=modifier.IDF)}
    elif hybrid_enabled:
        log.warning("qdrant.local_mode_dense_only", collection=name)

    await client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=vector_size, distance=distance),
        quantization_config=quantization_config,
        sparse_vectors_config=sparse_vectors_config,
    )
    return True
