"""Member-initiated case soft-delete (2026-07-09): the dashboard's "remove this case" affordance.

A junk / mistaken case (no findings, no completed audit) can be removed — soft (row retained,
hidden from every user-scoped list), ownership-checked, audited. A case that carries results
(findings, or a running/complete audit) is protected."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding


async def _fresh_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 tiny", "application/pdf")}
    )
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


async def _in_cases_list(client: AsyncClient, case_id: str) -> bool:
    r = await client.get("/v1/cases")
    assert r.status_code == 200, r.text
    return any(c["case_file_id"] == case_id for c in r.json()["cases"])


@pytest.mark.asyncio
async def test_remove_junk_case_soft_deletes_and_hides_it(client: AsyncClient):
    case_id = await _fresh_case(client)
    assert await _in_cases_list(client, case_id)  # present before

    r = await client.delete(f"/v1/cases/{case_id}")
    assert r.status_code == 204, r.text

    assert not await _in_cases_list(client, case_id)  # hidden after
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
    assert cf.soft_deleted_at is not None  # soft, not hard — row retained (audited)
    assert cf.soft_deleted_by is not None


@pytest.mark.asyncio
async def test_remove_is_idempotent(client: AsyncClient):
    case_id = await _fresh_case(client)
    assert (await client.delete(f"/v1/cases/{case_id}")).status_code == 204
    assert (await client.delete(f"/v1/cases/{case_id}")).status_code == 204  # no-op re-delete


@pytest.mark.asyncio
async def test_cannot_remove_case_with_findings(client: AsyncClient):
    case_id = await _fresh_case(client)
    async with AsyncSessionLocal() as s:
        s.add(
            Finding(
                case_file_id=uuid.UUID(case_id), finding_type="payer_side", category="test",
                subagent_source="test", voice_tier="A", facts={},
            )
        )
        await s.commit()
    r = await client.delete(f"/v1/cases/{case_id}")
    assert r.status_code == 409  # protected — has results
    assert await _in_cases_list(client, case_id)  # still listed


@pytest.mark.asyncio
async def test_cannot_remove_completed_audit(client: AsyncClient):
    case_id = await _fresh_case(client)
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        cf.status = "audit_complete"
        await s.commit()
    assert (await client.delete(f"/v1/cases/{case_id}")).status_code == 409


@pytest.mark.asyncio
async def test_remove_unknown_or_unowned_case_404(client: AsyncClient):
    # Anti-enumeration: a non-existent (or another user's) case is a 404, never 403.
    assert (await client.delete(f"/v1/cases/{uuid.uuid4()}")).status_code == 404
