"""The four V1-Lite Qdrant collections and their locked configs.

Embedding models and dims are locked per developer spec §7. NCCI/MUE tabular
rules live in Postgres (Phase 1C), NOT here — only narrative text goes into
error_detection_rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client.models import Distance


@dataclass(frozen=True)
class CollectionConfig:
    vector_size: int
    distance: Distance
    quantization: str  # "int8" (server-side quantization)
    embedding_model: str  # locked default; env can override (benchmarks only)
    hybrid_enabled: bool  # dense + BM25 sparse with RRF (server); dense-only in local mode
    requires_effective_date_filter: bool  # point-in-time filter mandatory


COLLECTIONS: dict[str, CollectionConfig] = {
    "billing_codes": CollectionConfig(
        vector_size=1024,
        distance=Distance.COSINE,
        quantization="int8",
        embedding_model="voyage-3-large",
        hybrid_enabled=True,
        requires_effective_date_filter=False,
    ),
    "error_detection_rules": CollectionConfig(
        vector_size=1024,
        distance=Distance.COSINE,
        quantization="int8",
        embedding_model="voyage-3-large",
        hybrid_enabled=True,
        requires_effective_date_filter=False,
    ),
    "laws_regulations": CollectionConfig(
        vector_size=1024,
        distance=Distance.COSINE,
        quantization="int8",
        embedding_model="voyage-context-3",
        hybrid_enabled=True,
        requires_effective_date_filter=True,
    ),
    "payer_policies": CollectionConfig(
        vector_size=1024,
        distance=Distance.COSINE,
        quantization="int8",
        embedding_model="voyage-3-large",
        hybrid_enabled=True,
        requires_effective_date_filter=True,
    ),
}

# Which payload field holds the text that gets embedded, per collection.
EMBED_TEXT_FIELD: dict[str, str] = {
    "billing_codes": "descriptor",
    "error_detection_rules": "narrative_text",
    "laws_regulations": "chunk_text",
    "payer_policies": "chunk_text",
}

# Stable business-key field per collection (used to derive deterministic point ids).
ID_FIELD: dict[str, str] = {
    "billing_codes": "code",
    "error_detection_rules": "rule_id",
    "laws_regulations": "chunk_id",
    "payer_policies": "chunk_id",
}
