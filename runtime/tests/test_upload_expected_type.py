"""Per-item checklist Add (Brock image-3, 2026-08-22): an upload can carry the document TYPE
it is expected to satisfy. The expectation is stamped on the stored document entry and a
classifier mismatch is measured (analytics), never silently absorbed — and never messaged with
engineering-invented copy (the wrongdoc voice is Brock's A4)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.case_files import CaseFile


@pytest.mark.asyncio
async def test_expected_type_stamped_and_mismatch_measured(client: AsyncClient):
    r = await client.post(
        "/v1/upload",
        files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))],
        data={"expected_type": "eob"},
    )
    assert r.status_code == 200, r.text
    case_id = r.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id))
            )
        ).scalar_one()
        assert cf.documents[0].get("expected_type") == "eob"
        # The fixture PDF cannot classify into the EOB family → the mismatch is measured.
        events = (
            await s.execute(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.event_name == "expected_document_mismatch"
                )
            )
        ).scalars().all()
        assert any(str(e.case_file_id) == case_id for e in events)


@pytest.mark.asyncio
async def test_unknown_expected_type_is_ignored(client: AsyncClient):
    r = await client.post(
        "/v1/upload",
        files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))],
        data={"expected_type": "passport"},
    )
    assert r.status_code == 200, r.text
    case_id = r.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id))
            )
        ).scalar_one()
        assert "expected_type" not in cf.documents[0]
