"""GET /v1/audit/{id} must never 500 on a non-dict agent-written finding column.

Live bug (2026-08-19 dev sweep, deductible_misapplied): an agent stored the literal
STRING 'null' as a finding's recommendation. The strict FindingOut raised
`dict_type` at response validation → the audit fetch 500'd, deterministically, on
every poll of that case. Same class as the 2026-07-09 citation-shape 500 — the
defensive projection now covers facts / legal_claim / recommendation themselves,
and every `(x or {}).get(...)` reader routes through schemas.case_file.as_dict
(a truthy non-empty string sails straight past `or {}`).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import _assemble_result
from app.crons.outcome_followup import _summary_for
from app.db.base import AsyncSessionLocal
from app.db.models.findings import Finding
from app.schemas.case_file import as_dict


def test_as_dict_reads_non_dicts_as_absent():
    assert as_dict({"a": 1}) == {"a": 1}
    assert as_dict("null") is None  # the live value
    assert as_dict(None) is None
    assert as_dict([1, 2]) is None
    assert as_dict("") is None


@pytest.mark.asyncio
async def test_assemble_result_tolerates_string_null_columns(client: AsyncClient):
    up = await client.post(
        "/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")}
    )
    assert up.status_code == 200, up.text
    case_id = up.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        s.add(
            Finding(
                case_file_id=uuid.UUID(case_id),
                finding_type="payer_side",
                category="cost_sharing_audit",
                subagent_source="math_person",
                voice_tier="B",
                # JSONB happily stores JSON strings — exactly what the agent wrote live.
                facts="null",
                legal_claim="null",
                recommendation="null",
            )
        )
        await s.commit()

    try:
        result = await _assemble_result(case_id, composed="")  # must NOT raise
        f = result.findings[0]
        assert f.facts == {} and f.legal_claim is None and f.recommendation is None

        # The route serializes it too (this is where the 500 actually surfaced).
        r = await client.get(f"/v1/audit/{case_id}")
        assert r.status_code == 200, r.text

        # The dashboard reads the same columns (_amount_saved_ytd crashed on this row
        # when the harness of this very test left it behind — proof by accident).
        r = await client.get("/v1/dashboard")
        assert r.status_code == 200, r.text
    finally:
        # Shared local DB: leave nothing behind (a persisted junk case broke the
        # dashboard tests until every reader was hardened — but tidiness still wins).
        from sqlalchemy import delete, select

        from app.db.models.case_files import CaseFile

        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == uuid.UUID(case_id)))
            row = (
                await s.execute(
                    select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id))
                )
            ).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()


def test_summary_reader_tolerates_string_null_recommendation():
    from types import SimpleNamespace

    junk = SimpleNamespace(category="x", recommendation="null", facts="null", voice_tier="B")
    assert _summary_for([junk]) == "your case"  # skipped, not crashed
