"""Phase CO-9 Module 2 — admin RAG/knowledge viewer tests (in-memory Qdrant).

Seeds billing_codes with one live + one staging chunk and exercises the admin routes.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from qdrant_client import models
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.knowledge.client import ensure_collection, get_client


@pytest_asyncio.fixture
async def seeded_qdrant(monkeypatch):
    import app.knowledge.client as kc

    monkeypatch.setattr(get_settings(), "qdrant_url", ":memory:")
    monkeypatch.setattr(get_settings(), "voyage_api_key", None)
    kc._client = None
    await ensure_collection("billing_codes", 1024)
    client = get_client()
    await client.upsert(
        collection_name="billing_codes",
        points=[
            models.PointStruct(
                id=1,
                vector=[0.1] * 1024,
                payload={"partition_status": "live", "code": "71045", "source": "cms_hcpcs"},
            ),
            models.PointStruct(
                id=2,
                vector=[0.1] * 1024,
                payload={"partition_status": "staging", "code": "70553", "source": "cms_hcpcs"},
            ),
        ],
    )
    yield
    kc._client = None


async def _user_action_payloads() -> list[dict]:
    async with AsyncSessionLocal() as s:
        rows = (
            (await s.execute(select(AuditEvent).where(AuditEvent.event_type == "user_action")))
            .scalars()
            .all()
        )
    return [json.loads(bytes(a.payload_encrypted).decode()) for a in rows]


@pytest.mark.asyncio
async def test_list_collections_returns_counts_per_partition(client: AsyncClient, seeded_qdrant):
    r = await client.get("/v1/admin/qdrant/collections")
    assert r.status_code == 200
    cols = {c["name"]: c for c in r.json()["collections"]}
    bc = cols["billing_codes"]
    assert bc["exists"] is True
    assert bc["total"] == 2 and bc["staging"] == 1 and bc["live"] == 1


@pytest.mark.asyncio
async def test_search_with_include_staging_returns_both(client: AsyncClient, seeded_qdrant):
    live_only = (
        await client.post(
            "/v1/admin/qdrant/collections/billing_codes/search", json={"query": "chest x-ray"}
        )
    ).json()
    assert len(live_only["results"]) == 1
    assert all(r["partition_status"] != "staging" for r in live_only["results"])

    both = (
        await client.post(
            "/v1/admin/qdrant/collections/billing_codes/search",
            json={"query": "chest x-ray", "include_staging": True},
        )
    ).json()
    assert len(both["results"]) == 2


@pytest.mark.asyncio
async def test_promote_chunk_changes_partition_status_writes_audit(
    client: AsyncClient, seeded_qdrant
):
    r = await client.post("/v1/admin/qdrant/collections/billing_codes/promote/2")
    assert r.status_code == 200
    detail = (await client.get("/v1/admin/qdrant/collections/billing_codes/chunk/2")).json()
    assert detail["partition_status"] == "live"
    assert detail["sample_review_status"] == "reviewed_pass"

    cols = {
        c["name"]: c
        for c in (await client.get("/v1/admin/qdrant/collections")).json()["collections"]
    }
    assert cols["billing_codes"]["staging"] == 0  # the promoted chunk left staging

    payloads = await _user_action_payloads()
    assert any(p.get("action") == "promote_chunk" and p.get("chunk_id") == "2" for p in payloads)


@pytest.mark.asyncio
async def test_promote_batch_writes_audit_per_chunk(client: AsyncClient, seeded_qdrant):
    r = await client.post(
        "/v1/admin/qdrant/collections/billing_codes/promote-batch",
        json={"chunk_ids": ["1", "2"]},
    )
    assert r.status_code == 200 and r.json()["promoted"] == 2
    payloads = await _user_action_payloads()
    promoted = {p.get("chunk_id") for p in payloads if p.get("action") == "promote_chunk"}
    assert {"1", "2"} <= promoted
