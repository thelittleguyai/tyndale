"""User-facing finding prose (e2e 2026-09-23 minors): no analyst-speak, no account holder's
full name, a [B] sentence never printed without its chip — at PROJECTION, rows untouched."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.sources.finding_prose import replace_account_holder, scrub_analyst_speak


def test_analyst_sentences_go_and_a_registry_line_stands_in_when_nothing_is_left():
    text = "The insurer applied the deductible twice. Legal claim is contingent on OOP max verification — omitted from primary finding until confirmed."
    out, hit = scrub_analyst_speak(text, "I need one more thing to firm this up.")
    assert hit and out == "The insurer applied the deductible twice."
    out, hit = scrub_analyst_speak("Omitted from the primary finding until confirmed.", "I need one more thing to firm this up.")
    assert hit and out == "I need one more thing to firm this up."
    assert scrub_analyst_speak("The bill lists two office visits.", "x") == ("The bill lists two office visits.", False)


def test_the_account_holders_name_becomes_you_with_the_verb_agreeing():
    out = replace_account_holder("Phil Fluegel was billed $7,600; Phil Fluegel's EOB says $538. The claim shows phil fluegel owes $538.", "Phil", "Fluegel")
    assert out == "You were billed $7,600; your EOB says $538. The claim shows you owe $538."
    assert replace_account_holder("Robert Fluegel was billed", "Phil", "Fluegel") == "Robert Fluegel was billed"  # not the holder
    assert replace_account_holder("x", None, "Fluegel") == "x"


@pytest.mark.asyncio
async def test_the_audit_endpoint_projects_clean_prose_and_keeps_the_row_verbatim(client: AsyncClient):
    from app.auth.dev_user import DEV_USER_ID, _ensure_dev_user_row
    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile
    from app.db.models.findings import Finding
    from app.db.models.users import User

    async with AsyncSessionLocal() as s:
        await _ensure_dev_user_row(s)
        me = (await s.execute(select(User).where(User.user_id == DEV_USER_ID))).scalar_one()
        me.first_name, me.last_name = "Amy", "Fluegel"
        await s.commit()
    up = await client.post("/v1/upload", files={"file": ("bill.pdf", b"%PDF-1.4 x", "application/pdf")})
    case_id = up.json()["case_file_id"]
    cid = uuid.UUID(case_id)
    raw_claim = "Amy Fluegel's insurer must reprocess the claim. Legal claim is contingent on OOP max verification — omitted from primary finding until confirmed."
    async with AsyncSessionLocal() as s:
        s.add(Finding(case_file_id=cid, finding_type="payer_side", category="cost_sharing_miscalculation", subagent_source="math_person",
                      voice_tier="B", facts={"gap": 120.0, "note": "Amy Fluegel was billed twice"}, legal_claim={"claim": raw_claim},
                      recommendation={"action": "Call the insurer; Amy Fluegel should quote the claim number."}))
        await s.commit()
    try:
        f = (await client.get(f"/v1/audit/{case_id}")).json()["findings"][0]
        assert f["legal_claim"]["claim"] == "Your insurer must reprocess the claim."
        assert f["facts"]["note"] == "You were billed twice"
        assert f["recommendation"]["action"] == "Call the insurer; you should quote the claim number."
        async with AsyncSessionLocal() as s:  # the stored row keeps the agent's exact words
            row = (await s.execute(select(Finding).where(Finding.case_file_id == cid))).scalar_one()
        assert row.legal_claim["claim"] == raw_claim
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == cid))
            row = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
            await s.commit()


@pytest.mark.asyncio
async def test_the_app_copy_surface_serves_the_not_found_screen(client: AsyncClient):
    from app.agents.context_loader import orchestration_step

    body = (await client.get("/v1/copy/app")).json()
    assert body["not_found_title"] == orchestration_step("app.not_found_title")
    assert body["not_found_cta"] == orchestration_step("app.not_found_cta") and body["not_found_body"]
