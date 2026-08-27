"""Chat-first event bridge (DL-91). The case thread is a pure, IDEMPOTENT projection of case
state: re-delivering a transition reconciles to the same thread (one status card, no duplicate
entries), and the thread is fully derivable from (status, line_items, findings) at any time. The
bridge is inert unless enable_chat_first_audit — the classic flow is untouched when off."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents import thread_bridge
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.db.models.messages import Message


@pytest.fixture
def chat_first_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_chat_first_audit", True)


async def _upload_new_case(client: AsyncClient) -> tuple[str, str | None]:
    r = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    assert r.status_code == 200, r.text
    b = r.json()
    return b["case_file_id"], b.get("conversation_id")


async def _messages(conversation_id: str) -> list[Message]:
    async with AsyncSessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(Message)
                    .where(Message.conversation_id == uuid.UUID(conversation_id))
                    .order_by(Message.sequence_number)
                )
            ).scalars().all()
        )


async def _set_case(case_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        for k, v in fields.items():
            setattr(cf, k, v)
        await s.commit()


def _li(code: str) -> dict:
    return {"line_item_id": str(uuid.uuid4()), "code": code, "code_system": "CPT",
            "raw_description": code, "plain_language_translation": "x", "example_scenarios": [],
            "high_risk": False, "billed_amount": 100.0, "units": 1}


@pytest.mark.asyncio
async def test_flag_off_is_a_noop(client: AsyncClient):
    r = await client.post(
        "/v1/upload", files=[("files", ("bill.pdf", b"%PDF-1.4 x", "application/pdf"))]
    )
    b = r.json()
    assert b["chat_first"] is False and b.get("conversation_id") is None  # classic flow untouched


@pytest.mark.asyncio
async def test_bootstrap_creates_thread_with_ack_and_status_card(client: AsyncClient, chat_first_on):
    _case_id, conv_id = await _upload_new_case(client)
    assert conv_id
    msgs = await _messages(conv_id)
    assert all(m.role == "system" for m in msgs)  # every bridge entry is system-authored
    assert sum(1 for m in msgs if m.kind == "status_card_update") == 1
    ack = next(m for m in msgs if m.payload.get("marker") == "ack")
    assert ack.content and "{{" not in ack.content  # {{doc_types}} slot interpolated, not raw


@pytest.mark.asyncio
async def test_reconcile_is_idempotent(client: AsyncClient, chat_first_on):
    case_id, conv_id = await _upload_new_case(client)
    before = await _messages(conv_id)
    await thread_bridge.bridge_case_state(case_id)  # deliver the same state twice more
    await thread_bridge.bridge_case_state(case_id)
    after = await _messages(conv_id)
    assert len(after) == len(before)  # no duplicates
    assert sum(1 for m in after if m.kind == "status_card_update") == 1  # ONE card, updated in place


@pytest.mark.asyncio
async def test_thread_derivable_from_state(client: AsyncClient, chat_first_on):
    case_id, conv_id = await _upload_new_case(client)

    # advance to encounter_verification_pending with 4 line items → verification cards (≤3/group)
    await _set_case(case_id, status="encounter_verification_pending",
                    line_items=[_li("99213"), _li("70553"), _li("36415"), _li("80053")])
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    verifs = [m for m in msgs if m.kind == "verification_request"]
    assert len(verifs) == 2  # 4 items → groups of 3 + 1
    assert all(len(m.payload["line_items"]) <= thread_bridge.VERIFICATION_GROUP_SIZE for m in verifs)
    card = next(m for m in msgs if m.kind == "status_card_update")
    assert {s["key"]: s["state"] for s in card.payload["stages"]}["encounter"] == "active"

    # advance to audit_complete with a three-number finding → the moment card + completion appear
    async with AsyncSessionLocal() as s:
        s.add(Finding(
            case_file_id=uuid.UUID(case_id), finding_type="payer_side",
            category="cost_sharing_miscalculation", subagent_source="math_person", voice_tier="A",
            facts={"provider_billed": 1200.0, "eob_member_responsibility": 800.0,
                   "tyndale_computed": 300.0},
        ))
        await s.commit()
    await _set_case(case_id, status="audit_complete")
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    moment = next(m for m in msgs if m.kind == "moment_card")
    assert moment.payload["variant"] == "three_number"
    assert moment.payload["delta"] == 500.0  # eob 800 - computed 300
    assert {s["state"] for s in next(m for m in msgs if m.kind == "status_card_update").payload["stages"]} == {"done"}
    # verification cards from the earlier state are still present (thread = full history)
    assert len([m for m in msgs if m.kind == "verification_request"]) == 2


@pytest.mark.asyncio
async def test_needs_documents_entry_carries_have_flags(client: AsyncClient, chat_first_on):
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(case_id, status="audit_incomplete", audit_incomplete_reason="needs_documents",
                    documents=[{"document_type": "bill", "filename": "bill.pdf"}], coverage=None)
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    nd = next(m for m in msgs if m.payload.get("marker") == "needs_documents")
    items = nd.payload["needs_documents"]["items"]
    by_key = {i["key"]: i["have"] for i in items}
    assert by_key == {"eob": False, "itemized_bill": True, "sbc": False}  # true have/need state


@pytest.mark.asyncio
async def test_extraction_failed_terminal_message(client: AsyncClient, chat_first_on):
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(case_id, status="extraction_failed")
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    term = next(m for m in msgs if m.payload.get("marker") == "terminal:extraction_failed")
    assert term.payload["tone"] == "error"
    card = next(m for m in msgs if m.kind == "status_card_update")
    assert card.payload["stages"][0]["state"] == "failed" and card.payload["terminal"]


# ── Brock 2026-08-22: while the machine works, the thread renders ONLY the status card ──

# A UMC-El-Paso-shaped page-1 statement: summary-only (no CPT rows, ledger labels, money),
# with the ledger label sitting on the PATIENT anchor line — the exact misextraction shape.
_UMC_SUMMARY_DOC = {
    "document_id": "doc-umc-1",
    "document_type": "bill",
    "extraction_status": "extracted",
    "ocr_text_chars": 400,
    "filename": "umc_statement.pdf",
    "ocr_text_preview": (
        "UNIVERSITY MEDICAL CENTER OF EL PASO    Page 1 of 4\n"
        "PATIENT: Payments (since last statements)\n"
        "STATEMENT SUMMARY\n"
        "Previous Balance    $2,480.00\n"
        "Payments (since last statements)    -$500.00\n"
        "New Balance    $1,980.00\n"
        "AMOUNT DUE    $1,980.00\n"
        "PLEASE PAY THIS AMOUNT\n"
        "Account Number 4471982\n"
    ),
}


async def test_machine_working_renders_only_the_status_card(client: AsyncClient, chat_first_on):
    """While the run is in-flight, content (dataquality notices, verification cards, handoff)
    queues — nothing renders alongside a spinning status card. It all appears on the first
    reconcile after the run pauses for input, with the card flagged paused."""
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id,
        status="audit_running",
        line_items=[_li("99213"), _li("85025")],
        documents=[_UMC_SUMMARY_DOC],
        regime_detection={"handoff": "pace"},
    )
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    assert not any(m.kind == "verification_request" for m in msgs)
    assert not any((m.payload or {}).get("data_quality") for m in msgs)
    assert not any((m.payload or {}).get("handoff") for m in msgs)
    card = next(m for m in msgs if m.kind == "status_card_update")
    assert card.payload["paused"] is False  # working, not waiting on the user

    # the run pauses for input → the queued content renders beneath a static (paused) card
    await _set_case(case_id, status="encounter_verification_pending")
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    assert any(m.kind == "verification_request" for m in msgs)
    summary_msg = next(
        m for m in msgs if (m.payload or {}).get("data_quality", {}).get("kind") == "summary_bill"
    )
    # audit 2026-08-27 group 3: the {itemized_request_script} slot resolves — the full
    # §5.2 string renders instead of degrading.
    assert "itemized statement" in (summary_msg.content or "")
    assert any((m.payload or {}).get("handoff") for m in msgs)
    card = next(m for m in msgs if m.kind == "status_card_update")
    assert card.payload["paused"] is True


def test_status_card_paused_only_when_awaiting_user_input():
    for status in ("encounter_verification_pending", "awaiting_eob_confirmation"):
        assert thread_bridge.status_card_payload(status)["paused"] is True
    for status in ("open", "in_progress", "audit_running", "audit_complete", "resolved"):
        assert thread_bridge.status_card_payload(status)["paused"] is False

async def test_ledger_furniture_patient_name_never_reaches_copy(client: AsyncClient, chat_first_on):
    """A pre-gate persisted junk patient_name ("Payments (since last statements)", the
    2026-08-22 UMC field test) is unknowable: it never triggers attest, never interpolates
    into any rendered copy, and verification proceeds normally."""
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id,
        status="encounter_verification_pending",
        patient_name="Payments (since last statements)",
        line_items=[_li("99213")],
    )
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    joined = " ".join(m.content or "" for m in msgs) + " ".join(
        str(m.payload) for m in msgs if m.payload
    )
    assert "Payments (since last statements)" not in joined
    assert not any((m.payload or {}).get("marker") == "attest:intro" for m in msgs)
    assert any(m.kind == "verification_request" for m in msgs)


async def test_ledger_furniture_never_reaches_any_payload_or_slot(client: AsyncClient, chat_first_on):  # noqa: F811
    """Audit 2026-08-27 item 5 — the three seams the first pass missed: the attest_request
    PAYLOAD, the reconcile.last_resort provider slot, and the moment-card context line.
    The UMC junk is persisted as BOTH names; nothing rendered may carry it."""
    junk = "Payments (since last statements)"
    case_id, conv_id = await _upload_new_case(client)
    await _set_case(
        case_id,
        status="audit_complete",
        patient_name=junk,
        provider_name=junk,
        line_items=[_li("99213")],
    )
    await thread_bridge.bridge_case_state(case_id)
    msgs = await _messages(conv_id)
    everything = " ".join((m.content or "") + " " + str(m.payload or {}) for m in msgs)
    assert junk not in everything
    # the moment card rendered (audit_complete + rung-2 anchor) — with no junk context
    moment = next((m for m in msgs if m.kind == "moment_card"), None)
    assert moment is not None
    assert junk not in str(moment.payload)
