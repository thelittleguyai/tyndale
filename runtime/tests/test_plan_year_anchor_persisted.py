"""The plan-year anchor outlives the intake (Brock 2026-09-21, decision 9 — doc 43).

The retention schedule keeps a plan year's EOBs through the end of THAT plan year, anchored on the
SBC's own "Coverage Period" (not the calendar year), else the member's answer to the plan-year ask.
The planner computed it on every step and threw it away; the case's coverage record now carries it
(coverage.plan_year_start + plan_year_start_source), written by the planner and by every upload.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.intake.timeline import persist_plan_year_start, resolved_plan_year_start

SBC_TEXT = "Summary of Benefits and Coverage   Coverage Period: 07/01/2026 – 06/30/2027   Plan Type: PPO"


def _case(**kw):
    return SimpleNamespace(**{"documents": [], "coverage": None, **kw})


def test_the_sbc_wins_then_the_answer_and_never_january_by_default():
    sbc_doc = {"document_type": "plan_summary", "ocr_text": SBC_TEXT}
    assert resolved_plan_year_start(_case()) == (None, None)  # unknown is unknown — no Jan 1
    answered = _case(coverage={"plan_effective_date": "2026-04-01"})
    assert resolved_plan_year_start(answered) == ("2026-04-01", "user")
    both = _case(documents=[sbc_doc], coverage={"plan_effective_date": "2026-04-01"})
    assert resolved_plan_year_start(both) == ("2026-07-01", "sbc")


def test_persisting_writes_the_coverage_record_once():
    c = _case(documents=[{"document_type": "sbc", "ocr_text": SBC_TEXT}], coverage={"deductible_amount": 2000})
    assert persist_plan_year_start(c) is True
    assert c.coverage == {"deductible_amount": 2000, "plan_year_start": "2026-07-01", "plan_year_start_source": "sbc"}
    assert persist_plan_year_start(c) is False  # nothing changed, nothing written
    assert persist_plan_year_start(_case()) is False  # nothing known, nothing written


@pytest.mark.asyncio
async def test_the_intake_and_the_upload_both_leave_it_on_the_case(client: AsyncClient, monkeypatch):
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        cf = CaseFile(user_id=u.user_id, status="open", intake_mode="guided", intake_status="in_progress",
                      documents=[], intake_state={"acked": ["welcome"]})
        s.add(cf)
        await s.commit()
        cfid = cf.case_file_id

    # the member answers the plan-year ask → the planner's next step persists the anchor
    r = await client.post("/v1/intake/answer", json={"case_file_id": str(cfid), "screen": "plan_year",
                                                    "action": "continue", "values": {"choice": "4"}})
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as s:
        cov = (await s.execute(select(CaseFile.coverage).where(CaseFile.case_file_id == cfid))).scalar_one()
    assert cov["plan_year_start_source"] == "user" and cov["plan_year_start"].endswith("-04-01")

    # an SBC uploaded onto the case replaces it with the plan's own coverage period
    import app.routes.upload as upload_route

    async def _sbc_ocr(_args):
        return {"ocr_text": SBC_TEXT, "extraction_status": "extracted"}

    monkeypatch.setattr(upload_route, "run_document_ocr", _sbc_ocr)
    r = await client.post("/v1/upload", data={"case_file_id": str(cfid)},
                          files=[("files", ("sbc.pdf", b"%PDF-1.4 sbc", "application/pdf"))])
    assert r.status_code == 200, r.text
    assert r.json()["uploads"][0]["document_type"] == "plan_summary"
    async with AsyncSessionLocal() as s:
        cov = (await s.execute(select(CaseFile.coverage).where(CaseFile.case_file_id == cfid))).scalar_one()
    assert (cov["plan_year_start"], cov["plan_year_start_source"]) == ("2026-07-01", "sbc")
