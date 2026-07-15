"""Server-side emission wiring (Internal Analytics P0). The headline guarantee (Brock): the
outcome-capture path is idempotent — a double-tapped outcome button can NEVER double-report. Also
smoke-checks that the upload funnel and thumbs mirror emit through the real routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent


async def _count(event_name: str, case_file_id: str) -> int:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.event_name == event_name)
                .where(AnalyticsEvent.case_file_id == uuid.UUID(case_file_id))
            )
        ).scalar_one()


async def _fresh_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


@pytest.mark.asyncio
async def test_upload_emits_funnel_events(client: AsyncClient):
    cid = await _fresh_case(client)
    assert await _count("upload_started", cid) >= 1
    assert await _count("documents_accepted", cid) >= 1
    assert await _count("extraction_succeeded", cid) >= 1


@pytest.mark.asyncio
async def test_outcome_report_is_idempotent_end_to_end(client: AsyncClient):
    """The P0 guarantee: three outcome reports for one case → exactly one outcome_reported row."""
    cid = await _fresh_case(client)
    for _ in range(3):
        r = await client.post(
            "/v1/feedback",
            json={
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "case_file_id": cid,
                "feedback_type": "outcome_report",
                "outcome": {"resolved": "yes", "amount_saved": 400.0},
            },
        )
        assert r.status_code == 200, r.text
    assert await _count("outcome_reported", cid) == 1  # can never double-report


@pytest.mark.asyncio
async def test_thumbs_mirrors_into_finding_feedback(client: AsyncClient):
    cid = await _fresh_case(client)
    r = await client.post(
        "/v1/feedback",
        json={
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_file_id": cid,
            "feedback_type": "thumbs",
            "response_id": "f1",
            "thumbs": "down",
        },
    )
    assert r.status_code == 200, r.text
    assert await _count("finding_feedback", cid) >= 1
