"""Sub-case summary view + gameplan (D5, Phase C §2 — DL-91). Honesty (§4) re-asserted at the
per-case grain: the three-number moment is None (never {0,0,0}) when the audit couldn't compute
it; recovered_so_far is CONFIRMED-only while identified is the labeled ESTIMATE; deadline clocks
come only from persisted rows. The gameplan orders biggest-dollar-first and renders one per-call
script per actionable finding, with the connective beats sourced from the orchestration script."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.sources.gameplan import build_gameplan


@pytest.fixture
def record_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_record_view", True)


async def _fresh_case(client: AsyncClient) -> str:
    up = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    assert up.status_code == 200, up.text
    return up.json()["case_file_id"]


async def _set(case_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        for k, v in fields.items():
            setattr(cf, k, v)
        await s.commit()


async def _user_of(case_id: str):
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile.user_id).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()


async def _finding(case_id: str, *, finding_type="payer_side", category="cost_sharing_miscalculation",
                   facts=None, recommendation=None, legal_claim=None) -> None:
    async with AsyncSessionLocal() as s:
        s.add(Finding(
            case_file_id=uuid.UUID(case_id), finding_type=finding_type, category=category,
            subagent_source="math_person", voice_tier="B", facts=facts or {},
            recommendation=recommendation, legal_claim=legal_claim,
        ))
        await s.commit()


async def _outcome(case_id: str, user_id, resolved: str, amount: float) -> None:
    async with AsyncSessionLocal() as s:
        s.add(FeedbackEvent(
            case_file_id=uuid.UUID(case_id), user_id=user_id, response_id="r",
            feedback_type="outcome_report", improvement_consent=False,
            payload={"outcome": {"resolved": resolved, "amount_saved": amount}},
        ))
        await s.commit()


# --- pure gameplan builder --------------------------------------------------
class _F:
    def __init__(self, ftype, gap, action):
        self.finding_id = uuid.uuid4()
        self.finding_type = ftype
        self.category = "cost_sharing_miscalculation"
        self.facts = {"gap": gap} if gap is not None else {}
        self.recommendation = {"action": action} if action else None
        self.legal_claim = {"claim": "The payer miscalculated cost-sharing."}


def test_gameplan_is_biggest_dollar_first_and_skips_actionless():
    steps = build_gameplan([
        _F("payer_side", 200.0, "Call to dispute the smaller item."),
        _F("provider_side", 900.0, "Call the provider about the big charge."),
        _F("payer_side", 500.0, None),  # no action → not a step
    ])
    assert [s.dollar_impact for s in steps] == [900.0, 200.0]  # biggest first, actionless dropped
    assert [s.index for s in steps] == [1, 2]
    assert steps[0].party == "provider" and steps[1].party == "payer"


def test_gameplan_step_has_all_four_call_beats():
    step = build_gameplan([_F("payer_side", 640.0, "Call your insurer to dispute the math.")])[0]
    sc = step.script
    assert sc.the_ask == "Call your insurer to dispute the math."
    assert sc.the_problem == "The payer miscalculated cost-sharing."  # finding's own Tier-B claim
    # connective beats come from the orchestration script (non-empty, not the MISSING marker)
    assert sc.when_they_pick_up and not sc.when_they_pick_up.startswith("<MISSING")
    assert sc.get_it_in_writing and sc.if_they_push_back and sc.if_they_push_back[0]
    assert "your insurance company" in sc.when_they_pick_up  # {{party}} interpolated


# --- endpoint ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_summary_hidden_when_flag_off(client: AsyncClient):
    a = await _fresh_case(client)
    assert (await client.get(f"/v1/case/{a}/summary")).status_code == 404


@pytest.mark.asyncio
async def test_summary_complete_case_three_number_and_recovered_and_gameplan(
    client: AsyncClient, record_on
):
    a = await _fresh_case(client)
    uid = await _user_of(a)
    await _finding(
        a,
        facts={"provider_billed": 1200, "eob_member_responsibility": 1200, "tyndale_computed": 560, "gap": 640},
        recommendation={"action": "Call the payer to dispute the cost-sharing math."},
        legal_claim={"claim": "The payer appears to have miscalculated member cost-sharing."},
    )
    await _set(a, status="audit_complete")
    await _outcome(a, uid, "yes", 400.0)  # confirmed recovery
    await _outcome(a, uid, "pending", 9999.0)  # must NOT count

    r = await client.get(f"/v1/case/{a}/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["three_number"]["tyndale_computed"] == 560.0
    assert body["recovered_so_far"] == 400.0  # CONFIRMED only, not the pending 9999
    assert body["identified_estimate"] == 640.0  # the ESTIMATE, surfaced separately
    assert body["status_banner"]["status"] == "audit_complete"
    assert len(body["gameplan"]) == 1
    assert body["gameplan"][0]["dollar_impact"] == 640.0
    assert body["gameplan"][0]["script"]["the_ask"].startswith("Call the payer")
    assert body["call_mode_intro"] and body["call_mode_outro"]


@pytest.mark.asyncio
async def test_summary_needs_documents_has_no_three_number_and_shows_checklist(
    client: AsyncClient, record_on
):
    a = await _fresh_case(client)
    await _set(a, status="audit_incomplete", audit_incomplete_reason="needs_documents")
    r = await client.get(f"/v1/case/{a}/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["three_number"] is None  # needs-documents, never {0,0,0}
    keys = {i["key"] for i in body["open_items"]}
    assert {"eob", "itemized_bill", "sbc"} <= keys  # the have/need checklist
    assert body["gameplan"] == []  # no actionable findings yet


@pytest.mark.asyncio
async def test_summary_deadline_clock_only_from_persisted_row(client: AsyncClient, record_on):
    a = await _fresh_case(client)
    await _set(a, status="audit_complete")
    # No deadline row yet → no clock invented from copy.
    r1 = await client.get(f"/v1/case/{a}/summary")
    assert r1.json()["status_banner"]["response_deadline"] is None
    # Persist a real deadline → the banner surfaces it with a provenance source.
    async with AsyncSessionLocal() as s:
        import datetime
        s.add(Deadline(
            case_file_id=uuid.UUID(a), deadline_type="erisa_internal_appeal",
            description="Internal appeal deadline", deadline_date=datetime.date(2026, 12, 31),
            status="pending",
        ))
        await s.commit()
    r2 = await client.get(f"/v1/case/{a}/summary")
    dl = r2.json()["status_banner"]["response_deadline"]
    assert dl is not None and dl["due_date"] == "2026-12-31" and dl["source"]


@pytest.mark.asyncio
async def test_summary_ownership_enforced(client: AsyncClient, record_on):
    # A random UUID the user doesn't own → 404 (IDOR guard), not 200/500.
    assert (await client.get(f"/v1/case/{uuid.uuid4()}/summary")).status_code == 404
