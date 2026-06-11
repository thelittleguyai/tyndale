"""Stub-route tests: /v1/audit returns the MRI fixture; /v1/feedback persists;
/v1/upload accepts a file."""

from __future__ import annotations

import datetime
import uuid

async def test_audit_returns_mri_fixture(client):
    # /v1/audit now requires an owned case (IDOR fix): create one via upload
    # first — the fixture path echoes whatever case_file_id it's given.
    up = await client.post(
        "/v1/upload", files={"file": ("bill.txt", b"sample bill", "text/plain")}
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]

    resp = await client.post("/v1/audit", json={"case_file_id": case_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_file_id"] == case_id
    assert body["audit"]["provider_billed"] == 1200.0
    assert body["audit"]["eob_member_responsibility"] == 1200.0
    assert body["audit"]["tyndale_computed"] == 560.0
    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["voice_tier"] == "B"
    assert finding["finding_type"] == "payer_side"
    assert finding["citations"][0]["src_id"].startswith("src_")


async def test_feedback_accepts_event(client):
    """Phase 2J — feedback returns FeedbackAck {event_id, feedback_event_id,
    queued_for_deid}. The dev user's consent is false by default, so the event
    is stored but not queued for de-id."""
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_file_id": str(uuid.uuid4()),
        "feedback_type": "thumbs",
        "thumbs": "up",
    }
    resp = await client.post("/v1/feedback", json=event)
    assert resp.status_code == 200
    body = resp.json()
    assert body["feedback_event_id"]
    # consent read server-side from the dev user (false by default) -> not queued
    assert body["queued_for_deid"] is False


async def test_feedback_consent_read_server_side_not_from_body(client):
    """Phase 2J / L05 — the client's claimed improvement_consent is IGNORED;
    the server reads the user's real consent. The dev user defaults to false,
    so even an event claiming consent=true does NOT queue for de-id."""
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "case_file_id": str(uuid.uuid4()),
        "feedback_type": "structured_correction",
        "structured_reason": ["wrong_number"],
        "improvement_consent": True,  # client claim — must be ignored
    }
    resp = await client.post("/v1/feedback", json=event)
    assert resp.status_code == 200
    assert resp.json()["queued_for_deid"] is False


async def test_upload_creates_case_and_returns_uuid(client):
    """Phase 2D — upload now persists the file + opens a real case file in
    Postgres. The returned case_file_id is a freshly-minted UUID (no longer
    the fixed MRI fixture id)."""
    content = b"STUB OCR - fixture bill content."
    files = {"file": ("bill.txt", content, "text/plain")}
    resp = await client.post("/v1/upload", files=files)
    assert resp.status_code == 200
    body = resp.json()
    # Real UUID, not the fixture id
    uuid.UUID(body["case_file_id"])
    uuid.UUID(body["document_id"])
    assert body["received_bytes"] == len(content)
    assert body["filename"] == "bill.txt"
