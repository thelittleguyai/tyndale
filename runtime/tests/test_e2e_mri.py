"""End-to-end MRI scenario tests — Phase 2D walking skeleton.

Replaces the manual curl-and-paste loop. Run via:

    uv run pytest tests/test_e2e_mri.py -v

The conftest.py fixture spins up an in-process ASGI client against the real
FastAPI app + the configured Postgres (DATABASE_URL). pytest's default
failure reporting includes full tracebacks, so when something blows up
inside a route, the exception lands in the test output directly — no more
generic 500s hiding the cause.

Three tiers of tests:

1. ``test_upload_*``                        — persistence + classification
2. ``test_audit_fixture_*``                 — fixture short-circuit (no API
                                              key needed; runs everywhere)
3. ``test_audit_real_claude_*``             — real Claude + DI roundtrip;
                                              skipped unless ANTHROPIC_API_KEY
                                              is set in env

Tier 1 + 2 are the diagnostic floor — if they pass, the route layer + DB
writes + fixture path all work. Tier 3 is the cost / behavior check for
real Claude orchestration.
"""

from __future__ import annotations

import os
import re
import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
def force_fixture_path(monkeypatch):
    """Force the orchestrator to take the fixture short-circuit regardless
    of whatever is in the developer's .env.local. Tests that assert against
    fixture values should depend on this."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "use_real_claude", False)
    yield


# ---------- Tier 1 — upload route ----------------------------------------------


@pytest.mark.asyncio
async def test_upload_persists_case_and_returns_uuid(client: AsyncClient) -> None:
    """Upload route should persist a CaseFile + return its UUID."""
    content = (
        b"HOSPITAL STATEMENT\n"
        b"CPT 70553 MRI brain w/o & w/ contrast\n"
        b"Billed: $1,200.00\n"
    )
    files = {"file": ("sample_mri.txt", content, "text/plain")}
    resp = await client.post("/v1/upload", files=files)
    assert resp.status_code == 200, f"upload failed: {resp.status_code} body={resp.text}"
    body = resp.json()
    # Fresh UUID, not the old fixed fixture id
    uuid.UUID(body["case_file_id"])
    uuid.UUID(body["document_id"])
    assert body["filename"] == "sample_mri.txt"
    assert body["received_bytes"] == len(content)
    # document_type classified from the stub OCR text — "bill" (CPT/Billed keywords)
    note = body.get("note") or ""
    assert "document_type" in note


@pytest.mark.asyncio
async def test_upload_classifies_eob(client: AsyncClient) -> None:
    """EOB keywords should land as document_type='eob'."""
    content = (
        b"EXPLANATION OF BENEFITS\n"
        b"Member Responsibility: $1,200.00\n"
    )
    files = {"file": ("eob.txt", content, "text/plain")}
    resp = await client.post("/v1/upload", files=files)
    assert resp.status_code == 200, f"body={resp.text}"
    # The stub OCR returns hardcoded bill-y text regardless of input, so the
    # classifier sees the stub's text — under USE_REAL_OCR=true the EOB
    # keywords above would route to 'eob'. Walking-skeleton test asserts
    # the classifier shape, not the specific value.
    assert "document_type" in (resp.json().get("note") or "")


@pytest.mark.asyncio
async def test_upload_two_uploads_create_distinct_cases(client: AsyncClient) -> None:
    """Two uploads should mint two distinct case_file_ids."""
    files = {"file": ("a.txt", b"first", "text/plain")}
    r1 = await client.post("/v1/upload", files=files)
    assert r1.status_code == 200, r1.text
    files = {"file": ("b.txt", b"second", "text/plain")}
    r2 = await client.post("/v1/upload", files=files)
    assert r2.status_code == 200, r2.text
    assert r1.json()["case_file_id"] != r2.json()["case_file_id"]


# ---------- Tier 2 — audit (fixture path; no API key required) -----------------


@pytest.mark.asyncio
async def test_audit_fixture_returns_three_numbers(
    client: AsyncClient, force_fixture_path
) -> None:
    """With USE_REAL_CLAUDE off (forced via fixture), audit returns the MRI
    canned response. Doesn't depend on what's in .env.local."""
    # Upload first to get a real case_file_id
    files = {"file": ("bill.txt", b"sample bill", "text/plain")}
    up = await client.post("/v1/upload", files=files)
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]

    resp = await client.post("/v1/audit", json={"case_file_id": case_id})
    assert resp.status_code == 200, f"audit failed: {resp.status_code} body={resp.text}"
    body = resp.json()

    a = body["audit"]
    assert a["provider_billed"] == 1200.0
    assert a["eob_member_responsibility"] == 1200.0
    assert a["tyndale_computed"] == 560.0

    assert len(body["findings"]) >= 1, "expected at least one finding from fixture"
    f0 = body["findings"][0]
    assert f0["voice_tier"] == "B"
    assert f0["finding_type"] == "payer_side"

    # Citation marker is in [authority §section, src_id] format
    marker = (f0.get("legal_claim") or {}).get("marker") or ""
    assert re.match(r"^\[.+, src_.+\]$", marker), (
        f"unexpected citation marker shape: {marker!r}"
    )


@pytest.mark.asyncio
async def test_audit_rejects_non_uuid(client: AsyncClient) -> None:
    """POST /v1/audit with a non-UUID returns 400 with a clear detail."""
    resp = await client.post("/v1/audit", json={"case_file_id": "not-a-uuid"})
    assert resp.status_code == 400
    assert "UUID" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_audit_get_idempotent(
    client: AsyncClient, force_fixture_path
) -> None:
    """GET /v1/audit/{id} returns the persisted state (used by the mobile poll)."""
    files = {"file": ("bill.txt", b"sample", "text/plain")}
    up = await client.post("/v1/upload", files=files)
    case_id = up.json()["case_file_id"]
    # POST once to materialize state
    await client.post("/v1/audit", json={"case_file_id": case_id})
    # GET should succeed
    resp = await client.get(f"/v1/audit/{case_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case_file_id"] == case_id


# ---------- Tier 2b — two-phase encounter-verification flow (Phase 2I) -------


async def _poll_status(client: AsyncClient, case_id: str, tries: int = 15) -> str:
    """Poll /status until audit_complete (or give up). With ASGITransport the
    finalize BackgroundTask has usually already run by the time /confirmations
    returns, so this resolves on the first try — the loop is just defensive."""
    import asyncio

    st = "unknown"
    for _ in range(tries):
        r = await client.get(f"/v1/audit/{case_id}/status")
        st = r.json()["status"]
        if st == "audit_complete":
            return st
        await asyncio.sleep(0.2)
    return st


async def _upload_and_extract(client: AsyncClient) -> tuple[str, list[dict]]:
    files = {"file": ("bill.txt", b"sample bill", "text/plain")}
    up = await client.post("/v1/upload", files=files)
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]
    ex = await client.post(f"/v1/audit/{case_id}/extract")
    assert ex.status_code == 200, ex.text
    body = ex.json()
    assert body["status"] == "encounter_verification_pending"
    assert body["intro_message"]
    assert len(body["line_items"]) >= 1
    return case_id, body["line_items"]


@pytest.mark.asyncio
async def test_extract_produces_plain_language_line_items(
    client: AsyncClient, force_fixture_path
) -> None:
    """/extract returns line items with plain-language translations + high_risk flags."""
    _case_id, line_items = await _upload_and_extract(client)
    for item in line_items:
        assert item["plain_language_translation"], "every line item needs a plain-language translation"
        assert "high_risk" in item
        assert item["code"]
    # At least one high-risk item exists (so the mismatch path is exercisable).
    assert any(it["high_risk"] for it in line_items)


@pytest.mark.asyncio
async def test_two_phase_flow_all_yes(client: AsyncClient, force_fixture_path) -> None:
    """All 'yes' confirmations → audit completes with the three numbers, no mismatch."""
    case_id, line_items = await _upload_and_extract(client)
    confirmations = [
        {"line_item_id": it["line_item_id"], "response": "yes", "user_note": None}
        for it in line_items
    ]
    cf = await client.post(f"/v1/audit/{case_id}/confirmations", json={"confirmations": confirmations})
    assert cf.status_code == 200, cf.text
    assert cf.json()["mismatches"] == 0

    status = await _poll_status(client, case_id)
    assert status == "audit_complete", f"status stuck at {status}"

    res = await client.get(f"/v1/audit/{case_id}")
    assert res.status_code == 200, res.text
    audit = res.json()["audit"]
    assert audit["provider_billed"] == 1200.0
    assert audit["eob_member_responsibility"] == 1200.0
    assert audit["tyndale_computed"] == 560.0
    types = [f["finding_type"] for f in res.json()["findings"]]
    assert "encounter_mismatch" not in types


@pytest.mark.asyncio
async def test_two_phase_flow_mismatch_creates_finding(
    client: AsyncClient, force_fixture_path
) -> None:
    """A 'no' on a high-risk line item → an encounter_mismatch finding appears."""
    case_id, line_items = await _upload_and_extract(client)
    high = next((it for it in line_items if it["high_risk"]), line_items[0])
    confirmations = []
    for it in line_items:
        is_target = it["line_item_id"] == high["line_item_id"]
        confirmations.append({
            "line_item_id": it["line_item_id"],
            "response": "no" if is_target else "yes",
            "user_note": "I was only there 20 minutes" if is_target else None,
        })
    cf = await client.post(f"/v1/audit/{case_id}/confirmations", json={"confirmations": confirmations})
    assert cf.status_code == 200, cf.text
    assert cf.json()["mismatches"] >= 1

    status = await _poll_status(client, case_id)
    assert status == "audit_complete", f"status stuck at {status}"

    res = await client.get(f"/v1/audit/{case_id}")
    types = [f["finding_type"] for f in res.json()["findings"]]
    assert "encounter_mismatch" in types, f"expected an encounter_mismatch finding, got {types}"


@pytest.mark.asyncio
async def test_confirmations_empty_returns_400(client: AsyncClient, force_fixture_path) -> None:
    """Submitting an empty confirmations list is a 400."""
    case_id, _ = await _upload_and_extract(client)
    r = await client.post(f"/v1/audit/{case_id}/confirmations", json={"confirmations": []})
    assert r.status_code == 400


# ---------- Tier 3 — real Claude + DI (skipped unless creds are set) -----------


_HAS_ANTHROPIC = bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.skipif(
    not _HAS_ANTHROPIC,
    reason="ANTHROPIC_API_KEY not set — skip real-Claude E2E",
)
@pytest.mark.asyncio
async def test_real_claude_mri_audit(monkeypatch, client: AsyncClient) -> None:
    """End-to-end with real Bill Detective + Math Person + Lead Planner.

    Cost ~$0.20–0.60 per run at Sonnet 4.6 list rates. Skips when
    ANTHROPIC_API_KEY is missing so CI without secrets stays green.
    """
    from app.config import get_settings

    monkeypatch.setenv("USE_REAL_CLAUDE", "true")
    get_settings.cache_clear()

    # Upload a more bill-shaped payload so the OCR path has plausible content
    content = (
        b"HOSPITAL STATEMENT\n"
        b"Date of service: 2026-03-14\n"
        b"CPT 70553 MRI brain w/o & w/ contrast - Billed $1,200.00\n"
        b"EXPLANATION OF BENEFITS\n"
        b"Allowed: $560.00\n"
        b"Member Responsibility: $1,200.00\n"
    )
    files = {"file": ("mri_bill.txt", content, "text/plain")}
    up = await client.post("/v1/upload", files=files)
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]

    resp = await client.post(
        "/v1/audit",
        json={"case_file_id": case_id},
        timeout=120.0,  # real Claude path can take a minute
    )
    assert resp.status_code == 200, f"real-claude audit failed: {resp.text}"
    body = resp.json()

    # Lead Planner should have composed something
    assert body["summary"], "lead planner produced no composed answer"
    # Math Person should have written at least one finding
    assert len(body["findings"]) >= 1, body
