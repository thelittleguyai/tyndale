"""Admin RAG / knowledge-base viewer (Phase CO-9, Module 2).

Browse the Qdrant collections, semantic-search them, inspect a chunk's full payload +
ingestion provenance, and promote a staging chunk to live.

DEVIATION (flagged): Qdrant payloads have no partition_status today (DL-59 staging lives in
Postgres for transparency_rates, not in Qdrant). So a chunk with no partition_status is
treated as 'live', and promote SETS the field — the machinery is in place for when
staging-in-Qdrant exists. Counts therefore show staging=0 until chunks are tagged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import models
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.session import get_session
from app.knowledge.client import get_client
from app.knowledge.collections import COLLECTIONS
from app.knowledge.embeddings import embed, model_for
from app.routes.admin._deps import admin_user, audit_admin_action

router = APIRouter(tags=["v1-admin"])

_STAGING = "staging"
_LIVE = "live"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _staging_filter() -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(key="partition_status", match=models.MatchValue(value=_STAGING))
        ]
    )


def _coerce_id(chunk_id: str):
    return int(chunk_id) if chunk_id.isdigit() else chunk_id


async def _count(client, name: str, partition: str | None = None) -> int:
    try:
        res = await client.count(
            collection_name=name,
            count_filter=_staging_filter() if partition == _STAGING else None,
            exact=True,
        )
        return int(res.count)
    except Exception:  # noqa: BLE001 — collection may not exist / local-mode quirks
        return 0


async def _sources(client, name: str, sample: int = 64) -> list[dict]:
    """Best-effort distinct sources + most-recent verified date from a payload sample."""
    try:
        points, _ = await client.scroll(
            collection_name=name, limit=sample, with_payload=True, with_vectors=False
        )
    except Exception:  # noqa: BLE001
        return []
    seen: dict[str, str] = {}
    for p in points:
        pl = p.payload or {}
        src = pl.get("source") or pl.get("payer") or pl.get("plan_type")
        if src:
            seen[str(src)] = max(seen.get(str(src), ""), str(pl.get("last_verified_date") or ""))
    return [{"source": k, "last_seen": v or None} for k, v in sorted(seen.items())]


@router.get("/admin/qdrant/collections")
async def list_collections(
    admin: CurrentUser = Depends(admin_user),
) -> dict[str, Any]:
    client = get_client()
    out: list[dict] = []
    for name in COLLECTIONS:
        exists = await client.collection_exists(name)
        if not exists:
            out.append(
                {"name": name, "exists": False, "total": 0, "live": 0, "staging": 0, "sources": []}
            )
            continue
        total = await _count(client, name)
        staging = await _count(client, name, _STAGING)
        out.append(
            {
                "name": name,
                "exists": True,
                "total": total,
                "live": total - staging,
                "staging": staging,
                "sources": await _sources(client, name),
            }
        )
    return {"collections": out}


class SearchRequest(BaseModel):
    query: str
    filters: dict[str, Any] | None = None
    limit: int = 20
    include_staging: bool = False


@router.post("/admin/qdrant/collections/{name}/search")
async def search_collection(
    name: str,
    req: SearchRequest,
    admin: CurrentUser = Depends(admin_user),
) -> dict[str, Any]:
    if name not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not Found")
    cfg = COLLECTIONS[name]
    vector = await embed(req.query, model_for(name), dim=cfg.vector_size)
    client = get_client()

    must = [
        models.FieldCondition(key=k, match=models.MatchValue(value=v))
        for k, v in (req.filters or {}).items()
    ]
    # Admin search is NOT effective-date filtered (admin sees everything). Staging is
    # excluded unless requested; points without partition_status count as live.
    must_not = (
        None
        if req.include_staging
        else [
            models.FieldCondition(key="partition_status", match=models.MatchValue(value=_STAGING))
        ]
    )
    qfilter = models.Filter(must=must or None, must_not=must_not)

    res = await client.query_points(
        collection_name=name,
        query=vector,
        limit=min(max(req.limit, 1), 100),
        query_filter=qfilter,
        with_payload=True,
    )
    return {
        "collection": name,
        "results": [
            {
                "id": str(p.id),
                "score": p.score or 0.0,
                "partition_status": (p.payload or {}).get("partition_status", _LIVE),
                "payload": p.payload or {},
            }
            for p in res.points
        ],
    }


@router.get("/admin/qdrant/collections/{name}/chunk/{chunk_id}")
async def chunk_detail(
    name: str,
    chunk_id: str,
    admin: CurrentUser = Depends(admin_user),
) -> dict[str, Any]:
    if name not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not Found")
    client = get_client()
    points = await client.retrieve(
        collection_name=name, ids=[_coerce_id(chunk_id)], with_payload=True, with_vectors=False
    )
    if not points:
        raise HTTPException(status_code=404, detail="Not Found")
    pl = points[0].payload or {}
    return {
        "collection": name,
        "id": str(points[0].id),
        "partition_status": pl.get("partition_status", _LIVE),
        "sample_review_status": pl.get("sample_review_status"),
        "last_sampled_at": pl.get("last_sampled_at"),
        "ingestion_provenance": {
            "source": pl.get("source") or pl.get("payer"),
            "source_file": pl.get("source_file"),
            "ingestion_run_id": pl.get("ingestion_run_id"),
            "last_verified_date": pl.get("last_verified_date"),
            "effective_date_start": pl.get("effective_date_start"),
            "effective_date_end": pl.get("effective_date_end"),
        },
        "payload": pl,
    }


async def _promote_one(client, name: str, chunk_id: str) -> None:
    await client.set_payload(
        collection_name=name,
        payload={
            "partition_status": _LIVE,
            "sample_review_status": "reviewed_pass",
            "last_sampled_at": _now_iso(),
        },
        points=[_coerce_id(chunk_id)],
    )


@router.post("/admin/qdrant/collections/{name}/promote/{chunk_id}")
async def promote_chunk(
    name: str,
    chunk_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if name not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not Found")
    await _promote_one(get_client(), name, chunk_id)
    await audit_admin_action(
        session,
        admin=admin,
        action="promote_chunk",
        extra={"collection": name, "chunk_id": chunk_id},
    )
    await session.commit()
    return {"ok": True, "collection": name, "chunk_id": chunk_id, "partition_status": _LIVE}


class PromoteBatchRequest(BaseModel):
    chunk_ids: list[str]


@router.post("/admin/qdrant/collections/{name}/promote-batch")
async def promote_batch(
    name: str,
    req: PromoteBatchRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if name not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="Not Found")
    client = get_client()
    for cid in req.chunk_ids:
        await _promote_one(client, name, cid)
        await audit_admin_action(
            session,
            admin=admin,
            action="promote_chunk",
            extra={"collection": name, "chunk_id": cid},
        )
    await session.commit()
    return {"ok": True, "collection": name, "promoted": len(req.chunk_ids)}
