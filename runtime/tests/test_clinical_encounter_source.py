"""CO-12D — ClinicalEncounterSource shim (UserUploadedVisitSummary).

The placeholder is replaced by a real thin shim over the Phase-2I encounter data on
CaseFile (line_items / encounter_confirmations / visit_context). resolve() returns it;
a populated case surfaces its data with a well-formed Provenance; an unknown / invalid
id degrades to the empty, not_available result without raising.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources import ClinicalEncounterSource, resolve
from app.sources.adapters.user_uploaded_visit_summary import UserUploadedVisitSummary


def test_resolve_returns_visit_summary_adapter():
    adapter = resolve(ClinicalEncounterSource)
    assert isinstance(adapter, UserUploadedVisitSummary)
    assert adapter.adapter_name == "UserUploadedVisitSummary"


@pytest.mark.asyncio
async def test_unknown_or_invalid_case_degrades_gracefully():
    res = await resolve(ClinicalEncounterSource).get_encounter(str(uuid.uuid4()))
    assert res.data["status"] == "not_available"
    assert res.data["line_items"] == []
    assert res.data["confirmations"] == []
    assert res.data["reason"] is None
    assert res.data["date_of_service"] is None
    assert res.provenance.adapter == "UserUploadedVisitSummary"
    assert res.provenance.source_kind == "user_upload"
    assert res.provenance.confidence == 0.0

    # A non-UUID id is equally graceful — no raise.
    res2 = await resolve(ClinicalEncounterSource).get_encounter("not-a-uuid")
    assert res2.data["status"] == "not_available"


@pytest.mark.asyncio
async def test_shim_surfaces_case_encounter_data(client: AsyncClient):
    up = await client.post("/v1/upload", files={"file": ("bill.txt", b"sample bill", "text/plain")})
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]

    line_items = [
        {
            "line_item_id": "li1",
            "code": "99284",
            "plain_language_translation": "A higher-complexity emergency room visit.",
        }
    ]
    confirmations = [{"line_item_id": "li1", "response": "yes", "user_note": None}]
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(CaseFile)
            .where(CaseFile.case_file_id == uuid.UUID(case_id))
            .values(
                line_items=line_items,
                encounter_confirmations=confirmations,
                visit_context="I went to the ER for chest pain.",
            )
        )
        await s.commit()

    res = await resolve(ClinicalEncounterSource).get_encounter(case_id)
    # data reflects the Phase-2I encounter record
    assert res.data["status"] == "available"
    assert res.data["date_of_service"] is None  # not captured pre-FHIR
    assert res.data["reason"] == "I went to the ER for chest pain."
    assert res.data["line_items"] == line_items
    assert res.data["confirmations"] == confirmations
    # well-formed Provenance
    assert res.provenance.adapter == "UserUploadedVisitSummary"
    assert res.provenance.source_kind == "user_upload"
    assert res.provenance.as_of is None
    assert res.provenance.confidence == 0.6
    assert any("date_of_service" in a for a in res.provenance.assumptions)
    assert any("not a clinical record" in a for a in res.provenance.assumptions)
