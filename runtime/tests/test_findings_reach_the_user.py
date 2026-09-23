"""Findings reach the user — thread AND results page (e2e 2026-09-23 M1).

The specimen's reveal was the three numbers + "nothing hidden" + a closing line: no finding
cards, no game plan, no link — the user had no path from the thread to a single finding, and
the results page's finding had no title on the audit endpoint. Now the thread projects every
surviving ERROR finding as a card (biggest dollar first, the honest no-dollar line when there
is no gap, BASIS chips only, what to do, the grounding line), then the "Your game plan" moment
that links to the results page; the audit endpoint carries `title`; and the sub-case brief
carries the informational typing so both results surfaces can show context under an explicit
expander instead of hiding it.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.agents import thread_bridge
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.db.models.messages import Message


@pytest.fixture
def flags_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)
    monkeypatch.setattr(get_settings(), "enable_record_view", True)


async def _upload(client: AsyncClient) -> tuple[str, str]:
    r = await client.post("/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))])
    assert r.status_code == 200, r.text
    return r.json()["case_file_id"], r.json()["conversation_id"]


def _finding(cid, category, *, finding_type="provider_side", facts=None, legal=None, rec=None, tier="A"):
    return Finding(case_file_id=cid, finding_type=finding_type, category=category, subagent_source="bill_detective",
                   voice_tier=tier, facts=facts or {}, legal_claim=legal, recommendation=rec)


@pytest.mark.asyncio
async def test_the_thread_carries_every_surviving_error_finding_and_a_link_to_the_results(client: AsyncClient, flags_on):
    case_id, conv_id = await _upload(client)
    cid = uuid.UUID(case_id)
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == cid))).scalar_one()
        cf.status = "audit_complete"
        s.add(_finding(cid, "upcoding", facts={"gap": 660.0, "billed_code": "01402"},
                       legal={"claim": "Anesthesia is billed by the surgery performed.", "citations": [{"authority": "CMS Anesthesia Guidelines", "section": "§50", "src_id": "src_a1"}]},
                       rec={"action": "Ask the surgery center to rebill the anesthesia under 01382."}, tier="B"))
        s.add(_finding(cid, "duplicate_charge", facts={"gap": 120.0}, rec={"action": "Ask for the duplicate line to be removed."}))
        s.add(_finding(cid, "phantom_service", finding_type="encounter_mismatch", facts={},  # no gap → the honest line
                       rec={"action": "Confirm with the provider whether this service happened."}))
        s.add(_finding(cid, "cost_sharing_audit", finding_type="payer_side", facts={"line_item_id": "li-1"}))  # informational
        s.add(_finding(cid, "unsourced", finding_type="payer_side", facts={"gap": 40.0}, tier="C",
                       legal={"downgraded": "no_retrieved_source", "unsourced": {"claim": "ACA says so"}, "citations_as_written": []},
                       rec={"action": "Ask.", "worth_checking": "Worth checking: there may be a rule behind this."}))
        await s.commit()
    try:
        await thread_bridge.bridge_case_state(case_id)
        async with AsyncSessionLocal() as s:
            msgs = list((await s.execute(select(Message).where(Message.conversation_id == uuid.UUID(conv_id)).order_by(Message.sequence_number))).scalars())
        cards = [m for m in msgs if m.kind == "moment_card" and (m.payload or {}).get("variant") == "finding"]
        # every surviving ERROR finding, biggest dollar first; the informational note is not a card
        assert [c.payload["title"] for c in cards] == ["Dispute the service level billed", "Duplicate charge", "Unsourced", "Phantom service"]
        assert [c.payload["amount"] for c in cards] == [660.0, 120.0, 40.0, None]
        up = cards[0].payload
        assert up["responsible_party"] == "provider" and up["claim"].startswith("Anesthesia") and up["tier"] == "rule_based"
        assert up["citations"] == [{"authority": "CMS Anesthesia Guidelines", "section": "§50", "src_id": "src_a1", "marker": "[CMS Anesthesia Guidelines, src_a1]"}]
        assert up["what_to_do"].startswith("Ask the surgery center") and up["has_source"]
        phantom = cards[3].payload
        assert phantom["amount_line"] == "No dollar change — still worth fixing." and phantom["responsible_party"] == "either"
        downgraded = cards[2].payload
        assert downgraded["claim"] is None and downgraded["citations"] == [] and downgraded["worth_checking"].startswith("Worth checking")
        header = next(m for m in msgs if (m.payload or {}).get("marker") == "findings:header")
        assert "4 problems" in header.content
        # the order: header → finding cards → the game plan → the closing line (the numbers
        # moment sits before all of these when the case carries document money; this fixture
        # has none, so rung-2 has no anchor and the moment is honestly absent)
        kinds = [(m.kind, (m.payload or {}).get("variant") or (m.payload or {}).get("marker")) for m in msgs]
        i_head = kinds.index(("system_message", "findings:header"))
        i_first = kinds.index(("moment_card", "finding"))
        i_plan = kinds.index(("moment_card", "gameplan"))
        i_done = kinds.index(("system_message", "completion"))
        assert i_head < i_first < i_plan < i_done
        plan = next(m for m in msgs if (m.payload or {}).get("variant") == "gameplan").payload
        assert plan["next_route"] == f"/audit/{case_id}" and plan["headline"] and plan["cta"]
        # idempotent: a second reconcile adds nothing
        await thread_bridge.bridge_case_state(case_id)
        async with AsyncSessionLocal() as s:
            again = list((await s.execute(select(Message).where(Message.conversation_id == uuid.UUID(conv_id)))).scalars())
        assert len(again) == len(msgs)

        # the API: every finding, each with a title; the sub-case brief types the context
        audit = (await client.get(f"/v1/audit/{case_id}")).json()
        assert sorted(f["title"] for f in audit["findings"]) == sorted(
            ["Dispute the service level billed", "Duplicate charge", "Phantom service", "Cost sharing audit", "Unsourced"])
        summary = (await client.get(f"/v1/case/{case_id}/summary")).json()
        by_cat = {f["category"]: f for f in summary["findings"]}
        assert by_cat["cost_sharing_audit"]["presentation"] == "informational_context"
        assert by_cat["upcoding"]["presentation"] is None
        # no finding exists in the API and is absent from both surfaces
        api_ids = {f["finding_id"] for f in audit["findings"]}
        thread_ids = {c.payload["finding_id"] for c in cards}
        page_ids = {f["finding_id"] for f in summary["findings"]}
        assert api_ids <= (thread_ids | page_ids) and api_ids == page_ids
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Finding).where(Finding.case_file_id == cid))
            await s.execute(delete(Message).where(Message.conversation_id == uuid.UUID(conv_id)))
            await s.commit()


@pytest.mark.asyncio
async def test_a_complete_audit_with_no_findings_still_links_to_its_results(client: AsyncClient, flags_on):
    case_id, conv_id = await _upload(client)
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))).scalar_one()
        cf.status = "audit_complete"
        await s.commit()
    try:
        await thread_bridge.bridge_case_state(case_id)
        async with AsyncSessionLocal() as s:
            msgs = list((await s.execute(select(Message).where(Message.conversation_id == uuid.UUID(conv_id)))).scalars())
        assert not any((m.payload or {}).get("variant") == "finding" for m in msgs)
        assert not any((m.payload or {}).get("marker") == "findings:header" for m in msgs)  # no "I found 0 problems"
        assert any((m.payload or {}).get("variant") == "gameplan" for m in msgs)  # the summary lives there too
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Message).where(Message.conversation_id == uuid.UUID(conv_id)))
            await s.commit()
