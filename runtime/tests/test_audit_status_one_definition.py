"""One definition of complete (e2e 2026-09-23 M4).

For ~4 minutes `/v1/audit/{id}` returned `status: complete` with findings while the case said
`audit_running` (the Lead Planner was composing) and the thread spun on "Writing your
summary". The endpoint's status now derives from the CASE: `summarizing` until terminal.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.routes.audit import api_audit_status


def test_the_mapping_from_case_status_to_api_status():
    assert api_audit_status("audit_complete", "complete") == "complete"
    assert api_audit_status("audit_incomplete", "audit_incomplete") == "audit_incomplete"
    for in_flight in ("audit_running", "encounter_verified"):
        assert api_audit_status(in_flight, "complete") == "summarizing"  # findings persisted ≠ done
    assert api_audit_status("encounter_verification_pending", "audit_incomplete") == "encounter_verification_pending"
    assert api_audit_status(None, "complete") == "complete"


@pytest.mark.asyncio
async def test_the_endpoint_never_says_complete_before_the_case_is_terminal(client: AsyncClient):
    up = await client.post("/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")})
    case_id = up.json()["case_file_id"]
    cid = uuid.UUID(case_id)
    async with AsyncSessionLocal() as s:
        # a persisted three-number finding — exactly the specimen's mid-run state
        s.add(Finding(case_file_id=cid, finding_type="payer_side", category="cost_sharing_audit", subagent_source="math_person",
                      voice_tier="A", facts={"provider_billed": 7600.0, "eob_member_responsibility": 538.0, "tyndale_computed": 538.0}))
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
        cf.status = "audit_running"
        await s.commit()
    try:
        body = (await client.get(f"/v1/audit/{case_id}")).json()
        assert body["status"] == "summarizing" and body["audit"] is not None  # the numbers exist; the run does not end here
        async with AsyncSessionLocal() as s:
            cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
            cf.status = "audit_complete"
            await s.commit()
        assert (await client.get(f"/v1/audit/{case_id}")).json()["status"] == "complete"
        async with AsyncSessionLocal() as s:
            cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
            cf.status = "encounter_verification_pending"
            await s.commit()
        assert (await client.get(f"/v1/audit/{case_id}")).json()["status"] == "encounter_verification_pending"
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == cid))
            row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()
