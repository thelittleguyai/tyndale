"""Chat-first event bridge (Phase A, Brock 2026-07-10 — DL-91).

Renders orchestrator case-state transitions into typed chat-thread entries. It holds NO state
machine of its own: the thread is a pure, IDEMPOTENT projection of case state
``(status, reason, documents, line_items, encounter_confirmations, findings)``. Re-running the
projection reconciles to the same thread — the single status card updates in place, and every
discrete entry is insert-if-absent keyed by a stable ``marker`` in its payload. This is exactly
the "thread content derivable from case state at any time" property the harness asserts.

System copy is loaded verbatim from the versioned orchestration script (D1); engineering never
edits it. Entirely inert unless ``settings.enable_chat_first_audit`` — the classic screen flow is
untouched when the flag is off.

Cycle note: this module is hooked FROM ``orchestrator._set_status`` (fire-and-forget), so it must
never import the orchestrator at module load — the few orchestrator helpers it needs
(``_assemble_result``, ``_documents_needed``, the honest-failure copy) are lazy-imported at call
time, after the orchestrator module is already initialized.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_loader import orchestration_step
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.conversations import Conversation
from app.db.models.messages import Message

log = structlog.get_logger(__name__)

VERIFICATION_GROUP_SIZE = 3  # D3: ≤3 verification cards per message

_STAGE_ORDER = ("extraction", "translate", "encounter", "audit")
_STAGE_LABEL_KEY = {
    "extraction": "stage_label_extraction",
    "translate": "stage_label_translate",
    "encounter": "stage_label_encounter",
    "audit": "stage_label_audit",
}
# The case status at/after which each flow stage is DONE. extraction+translate both complete when
# line items are ready (encounter_verification_pending) — there is no persisted status between
# upload and that point, so they fill together on that real transition (no fabricated progress).
_POST_TRANSLATE = {
    "encounter_verification_pending", "encounter_verified", "awaiting_eob_confirmation",
    "audit_running", "audit_complete", "audit_incomplete", "resolved", "archived",
}
_POST_ENCOUNTER = {
    "encounter_verified", "awaiting_eob_confirmation", "audit_running", "audit_complete",
    "audit_incomplete", "resolved", "archived",
}
_AUDIT_DONE = {"audit_complete", "audit_incomplete", "resolved", "archived"}
_DONE_AT = {"extraction": _POST_TRANSLATE, "translate": _POST_TRANSLATE,
            "encounter": _POST_ENCOUNTER, "audit": _AUDIT_DONE}
_EXTRACTION_FAILED = {"extraction_failed", "not_a_bill"}
_TERMINAL = {"audit_complete", "audit_incomplete", "extraction_failed", "not_a_bill",
             "resolved", "archived"}


def enabled() -> bool:
    return get_settings().enable_chat_first_audit


# --- status-card projection (pure) ------------------------------------------
def status_card_payload(status: str) -> dict:
    """The four flow-stage bars derived purely from case status (D2 — real completion, no
    fabricated percentages)."""
    terminal = status in _TERMINAL
    if status in _EXTRACTION_FAILED:
        # extraction couldn't produce a bill — mark it failed, the rest never ran.
        return {
            "stages": [
                {"key": k, "label": orchestration_step(_STAGE_LABEL_KEY[k]),
                 "state": "failed" if k == "extraction" else "pending"}
                for k in _STAGE_ORDER
            ],
            "terminal": True,
        }
    stages, active_assigned = [], False
    for key in _STAGE_ORDER:
        if status in _DONE_AT[key]:
            state = "done"
        elif not active_assigned and not terminal:
            state, active_assigned = "active", True
        else:
            state = "pending"
        stages.append({"key": key, "label": orchestration_step(_STAGE_LABEL_KEY[key]), "state": state})
    return {"stages": stages, "terminal": terminal}


def _doc_types_text(documents: list | None) -> str:
    """Human-joined distinct classified document types for the acknowledgment ({{doc_types}})."""
    friendly = {
        "bill": "bill", "itemized_bill": "itemized bill", "gfe": "good-faith estimate",
        "eob": "EOB", "ma_eob": "Medicare Advantage EOB", "msn": "Medicare Summary Notice",
        "tricare_eob": "TRICARE EOB", "insurance_card": "insurance card",
        "plan_summary": "plan summary", "denial_letter": "denial letter",
        "collections_notice": "collections notice", "mco_notice": "Medicaid notice",
        "va_statement": "VA statement", "community_care_auth": "community-care authorization",
    }
    seen: list[str] = []
    for d in documents or []:
        if isinstance(d, dict):
            name = friendly.get(d.get("document_type") or "", "document")
            if name not in seen:
                seen.append(name)
    if not seen:
        return "document"
    if len(seen) == 1:
        return seen[0]
    return ", ".join(seen[:-1]) + " and " + seen[-1]


# --- persistence helpers (mirror routes/messages.py) ------------------------
async def _next_seq(session: AsyncSession, conversation_id: uuid.UUID) -> int:
    row = (
        await session.execute(
            select(func.max(Message.sequence_number)).where(
                Message.conversation_id == conversation_id
            )
        )
    ).scalar_one_or_none()
    return (row or 0) + 1


async def _markers(session: AsyncSession, conversation_id: uuid.UUID) -> set[str]:
    """The `payload.marker` of every entry already in the thread — the idempotency ledger."""
    rows = (
        await session.execute(
            select(Message.payload).where(Message.conversation_id == conversation_id)
        )
    ).scalars().all()
    return {p["marker"] for p in rows if isinstance(p, dict) and p.get("marker")}


async def _insert(
    session: AsyncSession, conv: Conversation, kind: str, payload: dict | None = None,
    content: str | None = None, *, role: str = "system",
) -> Message:
    m = Message(
        conversation_id=conv.conversation_id,
        sequence_number=await _next_seq(session, conv.conversation_id),
        role=role,
        kind=kind,
        payload=payload,
        content=content,
        status="complete",
    )
    session.add(m)
    conv.message_count = (conv.message_count or 0) + 1
    conv.last_message_at = func.now()
    conv.updated_at = func.now()
    await session.flush()
    return m


async def _upsert_status_card(session: AsyncSession, conv: Conversation, payload: dict) -> None:
    """ONE status card per thread, updated in place (D2)."""
    existing = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conv.conversation_id)
            .where(Message.kind == "status_card_update")
            .order_by(Message.sequence_number)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.payload = {**payload, "marker": "status_card"}
        conv.updated_at = func.now()
        await session.flush()
    else:
        await _insert(session, conv, "status_card_update", {**payload, "marker": "status_card"})


async def get_case_conversation(
    session: AsyncSession, case_file_id: str, *, create_owner: uuid.UUID | None = None
) -> Conversation | None:
    """The canonical per-case thread (earliest non-archived conversation for the case). Creates
    one owned by `create_owner` when absent and an owner is supplied."""
    cid = uuid.UUID(case_file_id)
    conv = (
        await session.execute(
            select(Conversation)
            .where(Conversation.case_id == cid)
            .where(Conversation.is_archived.is_(False))
            .order_by(Conversation.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if conv is None and create_owner is not None:
        conv = Conversation(user_id=create_owner, case_id=cid)
        session.add(conv)
        await session.flush()
    return conv


# --- the projection ---------------------------------------------------------
async def bridge_case_state(case_file_id: str) -> None:
    """Reconcile the case's thread to its current state. Idempotent + fire-and-forget: any error is
    logged and swallowed so the bridge can NEVER break the audit path. No-op when the flag is off
    or the case has no conversation yet (bootstrap creates it)."""
    if not enabled():
        return
    try:
        async with AsyncSessionLocal() as session:
            case = (
                await session.execute(
                    select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_file_id))
                )
            ).scalar_one_or_none()
            if case is None:
                return
            conv = await get_case_conversation(session, case_file_id, create_owner=case.user_id)
            if conv is None:
                return
            await _reconcile(session, conv, case)
            await session.commit()
    except Exception:  # noqa: BLE001 — the bridge must never break the audit
        log.warning("thread_bridge.reconcile_failed", case_file_id=case_file_id, exc_info=True)


async def _reconcile(session: AsyncSession, conv: Conversation, case: CaseFile) -> None:
    status = case.status
    await _upsert_status_card(session, conv, status_card_payload(status))
    have = await _markers(session, conv.conversation_id)

    async def ensure(marker: str, kind: str, payload: dict, content: str | None = None) -> None:
        if marker not in have:
            await _insert(session, conv, kind, {**payload, "marker": marker}, content)
            have.add(marker)

    # acknowledgment (derivable from the uploaded documents)
    if case.documents:
        ack = orchestration_step("acknowledgment", doc_types=_doc_types_text(list(case.documents)))
        await ensure("ack", "system_message", {"text": ack, "tone": "neutral"}, ack)

    # verification cards — once line items exist, ≤3 per group (D3)
    line_items = list(case.line_items) if case.line_items else []
    if line_items:
        intro = orchestration_step("verification_intro")
        nudge = orchestration_step("verification_nudge")
        for gi in range(0, len(line_items), VERIFICATION_GROUP_SIZE):
            group = line_items[gi : gi + VERIFICATION_GROUP_SIZE]
            await ensure(
                f"verification:{gi // VERIFICATION_GROUP_SIZE}",
                "verification_request",
                {"intro": intro, "nudge": nudge, "group_index": gi // VERIFICATION_GROUP_SIZE,
                 "line_items": group},
            )

    # audit started (confirmations submitted → encounter_verified onward)
    if status in _POST_ENCOUNTER or status == "audit_running":
        start = orchestration_step("audit_start")
        await ensure("audit_start", "system_message", {"text": start, "tone": "neutral"}, start)

    # terminal states
    if status in _EXTRACTION_FAILED:
        from app.agents.orchestrator import EXTRACTION_FAILED_MESSAGE, not_a_bill_message

        if status == "not_a_bill":
            names = [d.get("filename", "your file") for d in (case.documents or []) if isinstance(d, dict)]
            text = not_a_bill_message(names)
        else:
            text = EXTRACTION_FAILED_MESSAGE
        await ensure(f"terminal:{status}", "system_message", {"text": text, "tone": "error"}, text)
    elif status == "audit_complete":
        await _ensure_three_number_moment(session, conv, case, ensure)
        done = orchestration_step("completion")
        await ensure("completion", "system_message", {"text": done, "tone": "neutral"}, done)
    elif status == "audit_incomplete":
        if case.audit_incomplete_reason == "system_error":
            text = orchestration_step("system_error")
            await ensure("terminal:system_error", "system_message", {"text": text, "tone": "error"}, text)
        else:  # needs_documents (default)
            await _ensure_needs_documents(session, conv, case, ensure)


async def _ensure_three_number_moment(session, conv, case, ensure) -> None:
    from app.agents.orchestrator import _assemble_result  # lazy — avoids the import cycle

    result = await _assemble_result(str(case.case_file_id), composed="")
    a = result.audit
    if a is None:
        return
    delta = round(a.eob_member_responsibility - a.tyndale_computed, 2)
    headline = orchestration_step("three_number_reveal", delta_dollars=f"{max(delta, 0):,.2f}")
    await ensure(
        "moment:three_number", "moment_card",
        {"variant": "three_number", "provider_billed": a.provider_billed,
         "eob_member_responsibility": a.eob_member_responsibility,
         "tyndale_computed": a.tyndale_computed, "delta": delta, "headline": headline},
    )


async def _ensure_needs_documents(session, conv, case, ensure) -> None:
    from app.agents.orchestrator import _documents_needed  # lazy — avoids the import cycle

    items = [
        {"key": d.key, "label": d.label, "how_to_get": d.how_to_get, "have": d.have}
        for d in _documents_needed(case)
    ]
    intro = orchestration_step("needs_documents_intro")
    await ensure(
        "needs_documents", "system_message",
        {"text": intro, "tone": "neutral", "needs_documents": {"intro": intro, "items": items}},
        intro,
    )


# --- bootstrap (called from the upload route when the flag is on) -----------
async def bootstrap_thread(case_file_id: str) -> str | None:
    """Create the case thread + seed the acknowledgment and status card. Returns the conversation
    id so the upload response can route the client there. No-op (returns None) when the flag is
    off. Idempotent — reuses an existing case conversation."""
    if not enabled():
        return None
    async with AsyncSessionLocal() as session:
        case = (
            await session.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_file_id))
            )
        ).scalar_one_or_none()
        if case is None:
            return None
        conv = await get_case_conversation(session, case_file_id, create_owner=case.user_id)
        await _reconcile(session, conv, case)
        await session.commit()
        return str(conv.conversation_id)


# --- verify-text writers (D4b, Phase B) — a free-text reply produces a SUGGESTION, never a
# confirmation (the tap commits). None of these touch case.encounter_confirmations or the status.
async def _post(
    case_file_id: str, *, role: str, kind: str, payload: dict | None = None, content: str | None = None
) -> str | None:
    async with AsyncSessionLocal() as session:
        case = (
            await session.execute(
                select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_file_id))
            )
        ).scalar_one_or_none()
        if case is None:
            return None
        conv = await get_case_conversation(session, case_file_id, create_owner=case.user_id)
        if conv is None:
            return None
        await _insert(session, conv, kind, payload, content=content, role=role)
        await session.commit()
        return str(conv.conversation_id)


async def post_user_utterance(case_file_id: str, text: str) -> str | None:
    """Persist the user's free-text verification reply as a user thread message."""
    return await _post(case_file_id, role="user", kind="message", content=text)


async def post_verification_suggestion(
    case_file_id: str, mappings: list[dict], summary: str
) -> str | None:
    """A pre-selectable suggestion (mapped cards + one confirm prompt). NOT a confirmation."""
    text = orchestration_step("verification_map_confirm", summary=summary)
    return await _post(
        case_file_id, role="system", kind="verification_suggestion",
        payload={"text": text, "summary": summary, "mappings": mappings}, content=text,
    )


async def post_verification_nudge(case_file_id: str, *, partial: bool) -> str | None:
    """The script-voiced 'please tap' fallback (D4a copy) when the utterance can't be mapped."""
    key = "verification_map_partial_fallback" if partial else "verification_map_fallback"
    text = orchestration_step(key)
    return await _post(
        case_file_id, role="system", kind="system_message",
        payload={"text": text, "tone": "neutral"}, content=text,
    )


async def post_system_line(case_file_id: str, text: str, *, tone: str = "neutral") -> str | None:
    """A one-off system line (e.g. the crisis decline surfaced in-thread)."""
    return await _post(
        case_file_id, role="system", kind="system_message",
        payload={"text": text, "tone": tone}, content=text,
    )
