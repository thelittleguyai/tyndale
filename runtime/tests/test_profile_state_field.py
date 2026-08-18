"""State of residence (2026-08-19, settings item 2).

Load-bearing properties: the patient-state grep is suggestion-grade and conservative
(patient block only — never the provider letterhead); jurisdiction selection lets the
case's own documents WIN over the profile default; the PATCH validates against the real
state vocabulary and never silently sets anything.
"""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.sources.extraction import grep_patient_state
from app.sources.jurisdiction import case_jurisdiction

BILL_TEXT = (
    "ACME HOSPITAL\n999 PROVIDER WAY\nCHICAGO, IL 60601\n\n"
    "PATIENT: JANE DOE\n123 MAIN ST\nBELOIT, WI 53511\n\n"
    "DATE OF SERVICE 03/14/2026"
)


def test_grep_patient_state_reads_the_patient_block_not_the_letterhead():
    assert grep_patient_state(BILL_TEXT) == "WI"  # not the provider's IL


def test_grep_patient_state_is_conservative():
    # No patient anchor → no suggestion, even with a state-zip shape present.
    assert grep_patient_state("ACME HOSPITAL\nCHICAGO, IL 60601") is None
    # A fake state code near the anchor → no suggestion.
    assert grep_patient_state("PATIENT: J DOE\nSOMEWHERE, ZZ 12345") is None


def test_case_jurisdiction_document_wins_profile_fills_unknown_degrades():
    doc_case = SimpleNamespace(case_file_id="c1", documents=[{"patient_state": "WI"}])
    assert case_jurisdiction(doc_case, "TX") == ("WI", "document")  # conflict: document wins
    assert case_jurisdiction(doc_case, None) == ("WI", "document")
    bare_case = SimpleNamespace(case_file_id="c2", documents=[])
    assert case_jurisdiction(bare_case, "TX") == ("TX", "profile")
    assert case_jurisdiction(bare_case, None) == (None, "unknown")


@pytest.mark.asyncio
async def test_patch_validates_state_and_roundtrips(client: AsyncClient):
    r = await client.patch("/v1/profile", json={"state": "ZZ"})
    assert r.status_code == 422  # not a jurisdiction

    r = await client.patch("/v1/profile", json={"state": "wi", "city": "Beloit"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "WI" and body["city"] == "Beloit"
    assert body["suggested_state"] is None  # set → no suggestion offered

    r = await client.patch("/v1/profile", json={"state": ""})
    assert r.status_code == 200 and r.json()["state"] is None


# ── secondary insurance (2026-08-19, item 4 — B6 groundwork, no COB math) ─────────────────
@pytest.mark.asyncio
async def test_secondary_insurance_crud_roundtrip(client: AsyncClient):
    # Empty state: no row, no hint (this dev user's cases carry no intake note here).
    r = await client.get("/v1/insurance/secondary")
    assert r.status_code == 200

    r = await client.put(
        "/v1/insurance/secondary",
        json={"insurer": "Acme Duo", "member_id": "DUO-77", "plan_type": "medicare_advantage"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True and body["insurer"] == "Acme Duo"
    assert body["plan_type"] == "medicare_advantage"

    # Primary endpoint is untouched by the secondary row.
    primary = (await client.get("/v1/insurance/info")).json()
    assert primary.get("insurer") != "Acme Duo" or primary.get("member_id") != "DUO-77"

    r = await client.put("/v1/insurance/secondary", json={"plan_type": "not_a_plan_type"})
    assert r.status_code == 422

    r = await client.delete("/v1/insurance/secondary")
    assert r.status_code == 204
    assert (await client.get("/v1/insurance/secondary")).json()["exists"] is False
