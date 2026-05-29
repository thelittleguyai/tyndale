"""Stub-route tests: /v1/audit returns the MRI fixture; /v1/feedback persists;
/v1/upload accepts a file."""

from __future__ import annotations

import datetime
import uuid

from app.stubs.fixtures import MRI_CASE_FILE_ID


async def test_audit_returns_mri_fixture(client):
    resp = await client.post("/v1/audit", json={"case_file_id": MRI_CASE_FILE_ID})
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_file_id"] == MRI_CASE_FILE_ID
    assert body["audit"]["provider_billed"] == 1200.0
    assert body["audit"]["eob_member_responsibility"] == 1200.0
    assert body["audit"]["tyndale_computed"] == 560.0
    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["voice_tier"] == "B"
    assert finding["finding_type"] == "payer_side"
    assert finding["citations"][0]["src_id"].startswith("src_")


async def test_feedback_accepts_event(client):
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_file_id": str(uuid.uuid4()),
        "feedback_type": "thumbs",
        "thumbs": "up",
        "improvement_consent": False,
    }
    resp = await client.post("/v1/feedback", json=event)
    assert resp.status_code == 200
    body = resp.json()
    assert body["stored"] is True
    assert body["feedback_event_id"]
    assert body["queued_for_triage"] is False


async def test_feedback_with_consent_queues_triage(client):
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_file_id": str(uuid.uuid4()),
        "feedback_type": "structured_correction",
        "structured_reason": ["wrong_number"],
        "improvement_consent": True,
    }
    resp = await client.post("/v1/feedback", json=event)
    assert resp.status_code == 200
    assert resp.json()["queued_for_triage"] is True


async def test_upload_creates_case_and_returns_uuid(client):
    """Phase 2D — upload now persists the file + opens a real case file in
    Postgres. The returned case_file_id is a freshly-minted UUID (no longer
    the fixed MRI fixture id)."""
    content = b"STUB OCR — fixture bill content."
    files = {"file": ("bill.txt", content, "text/plain")}
    resp = await client.post("/v1/upload", files=files)
    assert resp.status_code == 200
    body = resp.json()
    # Real UUID, not the fixture id
    uuid.UUID(body["case_file_id"])
    uuid.UUID(body["document_id"])
    assert body["received_bytes"] == len(content)
    assert body["filename"] == "bill.txt"
