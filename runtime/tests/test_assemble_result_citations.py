"""GET /v1/audit/{id} must never 500 on the shape of an agent-written citation.

Live bug (2026-07-09 dev sweep): 6/8 audit scenarios that produced findings-with-citations 500'd
in _assemble_result. Root cause: pg_store_finding persists citations as free-form dicts (the tool
schema is an open object), so real-Claude citations vary in their keys — but the projection did
`Citation(**c)`, which raises ValidationError on any dict missing the required src_id/marker.
Fixtures happen to write the exact shape, so unit tests passed while dev 500'd."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import _assemble_result
from app.db.base import AsyncSessionLocal
from app.db.models.findings import Finding


async def _case_with_citation_finding(client: AsyncClient, citations: list) -> str:
    up = await client.post(
        "/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")}
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        s.add(
            Finding(
                case_file_id=uuid.UUID(case_id), finding_type="payer_side", category="cost_share",
                subagent_source="math_person", voice_tier="B", facts={},
                legal_claim={"claim": "x", "citations": citations},
            )
        )
        await s.commit()
    return case_id


@pytest.mark.asyncio
async def test_assemble_result_tolerates_malformed_agent_citations(client: AsyncClient):
    case_id = await _case_with_citation_finding(
        client,
        [
            {"authority": "ACA §2713"},                    # missing src_id + marker — RAISED the 500
            {"title": "NSA overview", "source_id": "s1"},  # alias keys, no marker
            {"nonsense": 1},                               # nothing usable → dropped
            "not-a-dict",                                  # skipped
        ],
    )
    result = await _assemble_result(case_id, composed="")  # must NOT raise
    cites = result.findings[0].citations
    assert len(cites) == 2  # the two usable citations survive; empty/garbage dropped
    assert any("ACA" in c.marker for c in cites)  # marker synthesized from authority
    assert any(c.src_id == "s1" for c in cites)  # alias source_id → src_id


@pytest.mark.asyncio
async def test_assemble_result_preserves_well_formed_citation(client: AsyncClient):
    case_id = await _case_with_citation_finding(
        client,
        [{"authority": "ACA §2713", "src_id": "s9", "marker": "[ACA §2713, s9]", "section": "2713"}],
    )
    result = await _assemble_result(case_id, composed="")
    c = result.findings[0].citations[0]
    assert (c.authority, c.src_id, c.marker, c.section) == ("ACA §2713", "s9", "[ACA §2713, s9]", "2713")
