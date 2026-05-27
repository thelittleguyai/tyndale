"""Smoke tests for health + readiness."""

from __future__ import annotations


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


async def test_readiness_db_ok(client):
    resp = await client.get("/readiness")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"
