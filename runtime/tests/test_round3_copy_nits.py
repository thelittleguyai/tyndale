"""The round-3 copy and interpolation nits (e2e round 3 R6).

  * the example sheet carried every example gloss — an MSN gloss on the commercial SBC screen;
  * the wrong-document card ended "Here's what each one looks like…:" with nothing after it;
  * a paused needs_documents card showed ✓ on "Comparing your insurer's math" with no EOB.
(The acknowledgment naming the insurer as a bill's sender is pinned beside its siblings, in
tests/test_nothing_drops_under_a_working_card.py.)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.agents import thread_bridge
from app.agents.context_loader import orchestration_step
from app.agents.orchestrator import not_a_bill_message
from app.agents.wrongdoc import classify_wrong_document
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile


def _stages(payload: dict) -> dict[str, str]:
    return {s["key"]: s["state"] for s in payload["stages"]}


def test_a_stage_that_could_not_run_is_skipped_never_ticked():
    paused = thread_bridge.status_card_payload("audit_incomplete", incomplete_reason="needs_documents", has_eob=False)
    assert _stages(paused) == {"extraction": "done", "translate": "done", "encounter": "skipped", "audit": "waiting"}
    with_eob = thread_bridge.status_card_payload("audit_incomplete", incomplete_reason="needs_documents", has_eob=True)
    assert _stages(with_eob)["encounter"] == "done"
    done_bill_only = thread_bridge.status_card_payload("audit_complete", has_eob=False)
    assert _stages(done_bill_only)["encounter"] == "skipped" and done_bill_only["variant"] == "ready"
    # a case still working is not "skipped" — that is only a verdict on a finished run
    working = thread_bridge.status_card_payload("encounter_verification_pending", has_eob=False)
    assert "skipped" not in _stages(working).values()


def test_the_card_knows_whether_an_eob_is_on_file():
    from types import SimpleNamespace

    assert not thread_bridge._has_eob(SimpleNamespace(eobs=None, documents=[{"document_type": "bill"}]))
    assert thread_bridge._has_eob(SimpleNamespace(eobs=None, documents=[{"document_type": "msn"}]))
    assert thread_bridge._has_eob(SimpleNamespace(eobs=[{"payer": "Aetna"}], documents=[]))


def test_the_wrong_document_card_never_ends_on_a_lead_in_to_nothing():
    docs = [{"filename": "card.jpg", "document_type": "insurance_card", "extraction_status": "extracted"}]
    assert classify_wrong_document(docs) is not None
    text = not_a_bill_message(["card.jpg"], docs)
    assert "**itemized medical bill**" in text  # Brock's copy, verbatim up to there
    assert "Here's what each one looks like" not in text and not text.rstrip().endswith(":")
    assert text.rstrip().endswith("(EOB)**.")


@pytest.mark.asyncio
async def test_the_example_sheet_glosses_only_its_own_words(client: AsyncClient):
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        cf = CaseFile(
            user_id=u.user_id, status="open", intake_mode="guided", intake_status="in_progress",
            documents=[{"document_id": str(uuid.uuid4()), "document_type": "itemized_bill", "filename": "b.pdf",
                        "ocr_text": "99284 EMERGENCY DEPT VISIT 1,200.00"}],
            coverage={"payer_name": "Aetna", "member_id": "W1"},
            intake_state={"acked": ["welcome", "bill_summary"], "skipped": ["eob"]},
            regime_detection={"verified": True}, coverage_regime="erisa_self_funded",
        )
        s.add(cf)
        await s.commit()
        cfid = str(cf.case_file_id)
    sbc = (await client.get("/v1/intake/state", params={"case_file_id": cfid})).json()["screen"]
    assert sbc["id"] == "plan_rules"
    glosses = sbc["example"]["glosses"]
    assert "msn" not in glosses  # the commercial SBC screen: no Medicare gloss
    assert {"sbc", "deductible", "out_of_pocket"} <= set(glosses)
    assert glosses["sbc"] == orchestration_step("intake.example.gloss_sbc")
