"""Phase CO-6A — admin console runtime route tests.

The seeded dev user is `user_type='admin'` (DL-32), so the default test client is
admin. The non-admin path is tested by overriding the current_user dependency with
a regular user. DL-60: non-admin → 404 (anti-enumeration), never 403.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth import current_user
from app.auth.dev_user import CurrentUser
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.main import app
from app.middleware.rate_limit import global_limiter


# --------------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------------- #
async def _dev_admin_id() -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _fresh_case(**fields) -> str:
    uid = await _dev_admin_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status=fields.pop("status", "open"), **fields)
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _add_finding(case_file_id: str) -> str:
    async with AsyncSessionLocal() as s:
        f = Finding(
            case_file_id=uuid.UUID(case_file_id),
            finding_type="payer_side",
            category="cost_sharing_miscalculation",
            subagent_source="math_person",
            voice_tier="A",
            facts={"gap": 120.0},
            status="open",
        )
        s.add(f)
        await s.commit()
        return str(f.finding_id)


async def _add_audit_event(case_file_id: str) -> None:
    async with AsyncSessionLocal() as s:
        s.add(
            AuditEvent(
                event_type="tool_invocation",
                actor="bill_detective",
                case_file_id=uuid.UUID(case_file_id),
                payload_encrypted=b'{"tool_args_scrubbed": {"q": "x"}, "tool_result": {"ok": true}}',
                payload_hash=b"\x00" * 32,
                key_version=0,
                tools_invoked=["qdrant_search_payer_policies"],
                retrieved_chunks=[{"chunk_id": "ncd-220.4#1", "policy_id": "NCD-220.4"}],
                outcome="success",
            )
        )
        await s.commit()


@pytest.fixture
def as_non_admin():
    """Override current_user with a regular (non-admin) user for the 404 path."""
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=uuid.uuid4(), email="regular@example.com", first_name="Reg", user_type="user"
    )
    yield
    app.dependency_overrides.pop(current_user, None)


@pytest.fixture
def rate_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", True)
    global_limiter.reset()
    yield s
    global_limiter.reset()


# --------------------------------------------------------------------------- #
# Auth gate (DL-60)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_non_admin_user_gets_404_on_admin_routes(client: AsyncClient, as_non_admin):
    for path in ("/v1/admin/dashboard", "/v1/admin/cases"):
        r = await client.get(path)
        assert r.status_code == 404, f"{path}: {r.status_code}"  # 404, not 403 (anti-enumeration)


@pytest.mark.asyncio
async def test_admin_user_gets_200_on_dashboard(client: AsyncClient):
    r = await client.get("/v1/admin/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "open_cases_count" in body
    assert "pending_verdict_count" in body
    assert "recent_verdicts" in body
    assert body["shadow_appeals_pending"] == 0


# --------------------------------------------------------------------------- #
# Case detail + provenance
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_admin_user_gets_case_detail_with_full_provenance(client: AsyncClient):
    cfid = await _fresh_case(coverage={"deductible_amount": 2000, "deductible_met": 500})
    fid = await _add_finding(cfid)
    await _add_audit_event(cfid)

    detail = (await client.get(f"/v1/admin/cases/{cfid}")).json()
    assert detail["case_file_id"] == cfid
    assert detail["coverage"]["deductible_amount"] == 2000
    assert "documents" in detail
    assert any(f["finding_id"] == fid for f in detail["findings"])
    assert detail["conversation_history"] == []  # no chat model yet

    prov = (await client.get(f"/v1/admin/cases/{cfid}/provenance")).json()
    # All 7 provenance groups present (CO-002 Item 6.A).
    for key in (
        "documents",
        "skills_loaded",
        "tools_called",
        "qdrant_chunks_retrieved",
        "subagent_calls",
        "findings_written",
        "llm_calls",
    ):
        assert key in prov, f"missing provenance group: {key}"
    assert any(f["finding_id"] == fid for f in prov["findings_written"])
    assert len(prov["tools_called"]) >= 1  # the seeded tool_invocation
    assert len(prov["qdrant_chunks_retrieved"]) >= 1  # the seeded retrieved chunk


# --------------------------------------------------------------------------- #
# Verdict capture
# --------------------------------------------------------------------------- #
async def _verdict_row(verdict_id: str) -> AdminVerdict:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(
                select(AdminVerdict).where(AdminVerdict.verdict_id == uuid.UUID(verdict_id))
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_admin_verdict_persists_with_target_findings(client: AsyncClient):
    cfid = await _fresh_case()
    fid = await _add_finding(cfid)
    r = await client.post(
        f"/v1/admin/cases/{cfid}/verdict",
        json={"verdict": "hallucinated", "notes": "miscategorized", "target_findings": [fid]},
    )
    assert r.status_code == 200, r.text
    row = await _verdict_row(r.json()["verdict_id"])
    assert row.verdict == "hallucinated"
    assert row.target_findings == [fid]
    assert row.target_response is None


@pytest.mark.asyncio
async def test_admin_verdict_persists_with_target_response_only(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        f"/v1/admin/cases/{cfid}/verdict",
        json={"verdict": "partial", "target_response": "response-abc"},
    )
    assert r.status_code == 200, r.text
    row = await _verdict_row(r.json()["verdict_id"])
    assert row.target_response == "response-abc"
    assert row.target_findings is None


@pytest.mark.asyncio
async def test_admin_verdict_whole_case_persists_with_nulls(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(f"/v1/admin/cases/{cfid}/verdict", json={"verdict": "correct"})
    assert r.status_code == 200, r.text
    row = await _verdict_row(r.json()["verdict_id"])
    assert row.verdict == "correct"
    assert row.target_findings is None
    assert row.target_response is None


# --------------------------------------------------------------------------- #
# Dashboard counts + audit
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_admin_dashboard_returns_correct_counts(client: AsyncClient):
    a = await _fresh_case(status="open")
    await _fresh_case(status="open")
    await client.post(f"/v1/admin/cases/{a}/verdict", json={"verdict": "correct"})

    body = (await client.get("/v1/admin/dashboard")).json()
    assert body["open_cases_count"] >= 2  # at least the two just opened
    assert body["pending_verdict_count"] >= 1  # the un-verdicted open case
    assert any(v["case_file_id"] == a for v in body["recent_verdicts"])


@pytest.mark.asyncio
async def test_audit_event_written_on_verdict_submit(client: AsyncClient):
    cfid = await _fresh_case()
    await client.post(f"/v1/admin/cases/{cfid}/verdict", json={"verdict": "missed_finding"})
    async with AsyncSessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(AuditEvent)
                    .where(AuditEvent.case_file_id == uuid.UUID(cfid))
                    .where(AuditEvent.event_type == "user_action")
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    # MEDIUM-5 (2026-08-19): the cleartext actor column carries the admin's UUID now;
    # the email rides only in the encrypted payload.
    uuid.UUID(rows[0].actor)
    assert "@" not in rows[0].actor
    assert rows[0].outcome == "success"


# --------------------------------------------------------------------------- #
# Rate limiting (inherits Phase 2K.2 global limiter)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_admin_routes_rate_limited(client: AsyncClient, rate_on, monkeypatch):
    monkeypatch.setattr(rate_on, "rate_limit_per_ip_per_minute", 3)
    monkeypatch.setattr(rate_on, "rate_limit_per_ip_per_hour", 1000)
    headers = {"X-Forwarded-For": "203.0.113.55"}
    for i in range(3):
        r = await client.get("/v1/admin/dashboard", headers=headers)
        assert r.status_code != 429, f"req {i}: {r.status_code}"
    r = await client.get("/v1/admin/dashboard", headers=headers)
    assert r.status_code == 429
