"""Plan documents — the plan-level SBC home (2026-08-19, settings item 5).

Load-bearing properties: a plan-level SBC satisfies the SBC checklist line on EVERY
case (never re-asked per-case); its extracted terms feed rung-2 only where the case
states nothing of its own (case coverage wins field-by-field); and an SBC upload that
completes a stalled needs_documents case fires the same close-the-loop trigger as a
case upload.
"""

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents.orchestrator import _documents_needed, documents_all_satisfied
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.sources.plan_docs import merge_case_coverage

# Parenthesized "(SBC)" is the classifier's benefits-doc marker; the dollar/percent
# lines are what extract_sbc_from_text reads into rung-2's coverage keys.
_SBC_TEXT = (
    "Summary of Benefits and Coverage (SBC)\n"
    "Deductible individual $1,500\n"
    "Out-of-pocket max $6,000\n"
    "Coinsurance 20%\n"
)


def _stub_ocr(text: str):
    async def _run(args):
        return {"ocr_text": text, "extraction_status": "extracted"}

    return _run


def test_plan_sbc_satisfies_the_checklist_line():
    bare = SimpleNamespace(documents=[], coverage=None)
    assert not next(d for d in _documents_needed(bare) if d.key == "sbc").have
    assert next(d for d in _documents_needed(bare, plan_sbc=True) if d.key == "sbc").have

    # With EOB + bill on the case, the plan-level SBC is the LAST missing input.
    docs = [{"document_type": "eob"}, {"document_type": "itemized_bill"}]
    stalled = SimpleNamespace(documents=docs, coverage=None)
    assert not documents_all_satisfied(stalled)
    assert documents_all_satisfied(stalled, plan_sbc=True)


def test_merge_case_coverage_case_wins_plan_fills():
    case_cov = {"deductible_amount": 500.0, "coinsurance_percent": None}
    plan_cov = {"deductible_amount": 1500.0, "coinsurance_percent": 20.0}
    merged = merge_case_coverage(case_cov, plan_cov)
    assert merged["deductible_amount"] == 500.0  # the case's own document wins
    assert merged["coinsurance_percent"] == 20.0  # the plan SBC fills the gap
    assert merge_case_coverage(None, None) is None
    assert merge_case_coverage(case_cov, None) is case_cov


@pytest.mark.asyncio
async def test_plan_document_upload_roundtrip_and_reaudit_trigger(
    client: AsyncClient, monkeypatch
):
    import app.routes.plan_documents as pd_route

    monkeypatch.setattr(pd_route, "run_document_ocr", _stub_ocr(_SBC_TEXT))

    finalized: list[str] = []

    async def _fake_finalize(cfid: str):
        finalized.append(cfid)

    monkeypatch.setattr(pd_route, "finalize_audit", _fake_finalize)

    # A stalled case with EOB + bill already on file — the SBC is its last missing input.
    async with AsyncSessionLocal() as s:
        any_case = (await s.execute(select(CaseFile).limit(1))).scalar_one()
        stalled = CaseFile(
            user_id=any_case.user_id,
            status="audit_incomplete",
            audit_incomplete_reason="needs_documents",
            documents=[
                {"document_id": str(uuid.uuid4()), "document_type": "eob"},
                {"document_id": str(uuid.uuid4()), "document_type": "itemized_bill"},
            ],
        )
        s.add(stalled)
        await s.commit()
        stalled_id = str(stalled.case_file_id)

    r = await client.post(
        "/v1/plan/documents",
        files={"file": ("my-sbc.pdf", b"%PDF-1.4 sbc bytes", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_sbc"] is True and body["has_coverage_terms"] is True

    listing = (await client.get("/v1/plan/documents")).json()
    assert listing["sbc_on_file"] is True
    assert any(d["plan_document_id"] == body["plan_document_id"] for d in listing["documents"])

    # Close-the-loop: the stalled case was completed by this PLAN-level upload.
    assert stalled_id in finalized

    # Not-a-document payloads still fail fast at the door.
    bad = await client.post(
        "/v1/plan/documents", files={"file": ("notes.txt", b"grocery list", "text/plain")}
    )
    assert bad.status_code == 422

    r = await client.delete(f"/v1/plan/documents/{body['plan_document_id']}")
    assert r.status_code == 204
    assert (await client.get("/v1/plan/documents")).json()["sbc_on_file"] is False

    async with AsyncSessionLocal() as s:  # cleanup the synthetic stalled case
        row = (
            await s.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(stalled_id))
            )
        ).scalar_one()
        await s.delete(row)
        await s.commit()
