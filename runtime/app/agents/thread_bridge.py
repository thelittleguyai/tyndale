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
from collections import Counter

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_loader import orchestration_step
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.conversations import Conversation
from app.db.models.messages import Message

log = structlog.get_logger(__name__)

VERIFICATION_GROUP_SIZE = 3  # D3: ≤3 verification cards per message

# Marker collisions caught by the partial unique index (migration 0039), since boot. A losing
# writer is HARMLESS — the entry exists exactly once either way — but it is counted so the race
# stops being invisible. Surfaced on the admin ops panel alongside the analytics drop counts.
BRIDGE_CONFLICTS: Counter[str] = Counter()


def get_bridge_conflicts() -> dict[str, int]:
    return dict(BRIDGE_CONFLICTS)


# Every registry key this module can put in front of a user (deep review nit 3). A key missing
# from the registry renders as the literal marker `<MISSING-script: key>` — visible, testable,
# and exactly the wrong thing to discover in production. `assert_production_safety` refuses a
# staging/prod boot when any of these is absent, so a malformed or truncated future copy drop
# fails at startup instead of shipping markers into threads.
#
# Kept as an explicit list rather than derived at runtime, because a boot gate shouldn't parse
# its own source. `test_required_keys_manifest.py` walks this module's AST and fails if a
# literal key is rendered that isn't listed here, so the two can't drift.
RENDER_PATH_KEYS: frozenset[str] = frozenset(
    {
        # status card + flow stages
        "stage_label_extraction", "stage_label_translate", "stage_label_encounter",
        "stage_label_audit",
        # intake + acknowledgment
        "record_first_upload_frame", "acknowledgment", "audit_start",
        # attest-and-proceed
        "attest.intro", "attest.decline_ack",
        # verification
        "verification_intro", "verification_map_confirm", "verification_not_sure",
        "verification_nudge",
        # data quality
        "dataquality_partial_illegible", "dataquality_summary_not_itemized",
        # reconcile ladder
        "reconcile.explain", "reconcile.ask_one_input", "reconcile.last_resort",
        # the reveal + terminal states
        "three_number_reveal", "completion", "needs_documents_intro", "system_error",
        "system_error_no_email",  # §10.4 minus the email clause, while the flag is off
        "record_post_audit_keep_doing",
        # rung-2 unlock-more (complete-with-missing-inputs; eng placeholders, asks §3.11)
        "unlock_more.intro", "unlock_more.item_hint",
        # chosen dynamically at the call site, so both branches must exist
        "handoff.pace", "handoff.generic_program",
        "verification_map_fallback", "verification_map_partial_fallback",
    }
)

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
             "resolved", "archived", "attest_declined"}


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


def _payer_of(case) -> str | None:
    """The insurer name for {payer} (§1.4) from TYPED coverage/EOB fields — None when unknown,
    which degrades rather than naming an insurer we didn't extract."""
    cov = getattr(case, "coverage", None) or {}
    for key in ("payer", "payer_name", "insurer", "plan_name"):
        v = cov.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for e in (getattr(case, "eobs", None) or []):
        if isinstance(e, dict):
            v = e.get("payer") or (e.get("eob") or {}).get("payer")
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _program_source(handoff: str | None) -> str | None:
    """The citation for {program_source} (§12.1). None until the program corpus carries one —
    his string is [A]/[B] and must never render a sourceless program claim."""
    return None


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
        ack = orchestration_step(
            "acknowledgment",
            doc_list=_doc_types_text(list(case.documents)),
            payer=_payer_of(case),
        )
        await ensure("ack", "system_message", {"text": ack, "tone": "neutral"}, ack)

    # Attest-and-proceed (§A2 state 1) — evaluated on EVERY reconcile, which is the backfill
    # guard: an existing case with a name mismatch and no attestation gets the prompt on next
    # open, never silently grandfathered. The attest entry renders BEFORE encounter
    # verification, and the verification cards hold until attested.
    from app.agents.attest import RELATIONSHIPS, evaluate_attest_state
    from app.db.models.users import User

    attest_user = (
        await session.execute(select(User).where(User.user_id == case.user_id))
    ).scalar_one_or_none()
    attest_needed = evaluate_attest_state(case, attest_user) if attest_user else False
    if attest_needed:
        intro = orchestration_step(
            "attest.intro",
            patient_name=case.patient_name,
            first_name=(getattr(attest_user, "first_name", None) or "there"),
        )
        await ensure(
            "attest",
            "attest_request",
            {
                "intro": intro,
                "patient_name": case.patient_name,
                "menu": [
                    {"key": k, "label": orchestration_step(f"attest.menu_{k}")}
                    for k in RELATIONSHIPS
                ],
                "decline_key": "not_authorized",
            },
            intro,
        )
    if status == "attest_declined":
        text = orchestration_step("attest.decline_ack")
        await ensure("terminal:attest_declined", "system_message", {"text": text, "tone": "neutral"}, text)
        return  # closed gracefully — nothing downstream renders

    # F3 §5.1 — a PARTIAL read: run what's readable, name the unreadable part, ask for the one
    # fix. Never a guessed number (data_quality.never_approximate documents that rule).
    from app.sources.data_quality import looks_like_summary_bill, partial_read

    docs = [d for d in (case.documents or []) if isinstance(d, dict)]
    partial = partial_read(docs)
    if partial:
        text = orchestration_step("dataquality_partial_illegible", line_desc=partial["unreadable_label"])
        await ensure(
            "dataquality:partial", "system_message",
            {"text": text, "tone": "neutral",
             "data_quality": {"kind": "partial_read", **partial}},
            text,
        )

    # F4 §5.2 — a summary statement rather than an itemised bill: coach the request instead of
    # auditing a total. {itemized_request_script} has no authored value yet, so the string
    # degrades rather than inventing a script (flagged for Brock).
    if any(looks_like_summary_bill(d) for d in docs):
        text = orchestration_step("dataquality_summary_not_itemized")
        await ensure(
            "dataquality:summary_bill", "system_message",
            {"text": text, "tone": "neutral", "data_quality": {"kind": "summary_bill"}},
            text,
        )

    # verification cards — once line items exist, ≤3 per group (D3); held behind attest
    line_items = [] if attest_needed else (list(case.line_items) if case.line_items else [])
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

    # External-program handoff (§A2 state 5 / script §12). Regime detection already routes
    # PACE to a handoff seam; this is the user-facing beat. Warm, with the program's own
    # contact path — and the case STAYS OPEN ("I'm still here for the billing side"), which is
    # what keeps this X1-compliant rather than a hand-off-and-drop.
    handoff = (case.regime_detection or {}).get("handoff")
    if handoff:
        key = "handoff.pace" if handoff == "pace" else "handoff.generic_program"
        text = orchestration_step(
            key,
            program_name=(handoff.upper() if handoff else None),
            program_source=_program_source(handoff),
        )
        marker = f"handoff:{handoff}"
        first_time = marker not in have  # emit once, not on every reconcile
        await ensure(
            marker,
            "system_message",
            {"text": text, "tone": "neutral", "handoff": {"program": handoff, "case_stays_open": True}},
            text,
        )
        if first_time:
            from app.analytics.emit import emit

            await emit(
                "program_handoff_shown",
                user_id=case.user_id,
                case_file_id=case.case_file_id,
                properties={"program": handoff if handoff == "pace" else "other"},
            )

    # audit started (confirmations submitted → encounter_verified onward)
    if status in _POST_ENCOUNTER or status == "audit_running":
        start = orchestration_step("audit_start")
        await ensure("audit_start", "system_message", {"text": start, "tone": "neutral"}, start)

    # terminal states
    if status in _EXTRACTION_FAILED:
        from app.agents.orchestrator import EXTRACTION_FAILED_MESSAGE, not_a_bill_message

        if status == "not_a_bill":
            docs = [d for d in (case.documents or []) if isinstance(d, dict)]
            names = [d.get("filename", "your file") for d in docs]
            text = not_a_bill_message(names, docs)
            # §A2 state 2: carry the typed branch + its next step so the thread offers a real
            # affordance (card-upload flow / attach-to-coverage / add a bill), never a dead end.
            from app.agents.wrongdoc import classify_wrong_document

            wrong = classify_wrong_document(docs)
            extra = (
                {"wrongdoc_branch": wrong.branch, "next_action": wrong.next_action}
                if wrong
                else {}
            )
        else:
            text = EXTRACTION_FAILED_MESSAGE
            extra = {}
        await ensure(
            f"terminal:{status}", "system_message", {"text": text, "tone": "error", **extra}, text
        )
    elif status == "audit_complete":
        await _ensure_three_number_moment(session, conv, case, ensure)
        await _ensure_reconcile_state(session, conv, case, ensure)
        done = orchestration_step("completion")
        await ensure("completion", "system_message", {"text": done, "tone": "neutral"}, done)
        # Rung-2 follow-through: a COMPLETED audit that ran with documents missing offers the
        # same have/need checklist re-framed as "this deepens your audit" — an unlock, never a
        # gate (the SBC-gate removal, 2026-08-18). The true-gate case keeps needs_documents.
        await _ensure_unlock_more(session, conv, case, ensure)
    elif status == "audit_incomplete":
        if case.audit_incomplete_reason == "system_error":
            # §10.4's closing clause promises "I'll email you the moment I've got it working
            # again." That email exists now (notify.send_recovery_email) but only sends where
            # enable_audit_ready_email is on — so the clause renders ONLY there, D3-style: the
            # no-email variant is the same message without the promise (eng seed, asks §3.9).
            key = (
                "system_error"
                if get_settings().enable_audit_ready_email
                else "system_error_no_email"
            )
            text = orchestration_step(key)
            await ensure("terminal:system_error", "system_message", {"text": text, "tone": "error"}, text)
        else:  # needs_documents (default)
            await _ensure_needs_documents(session, conv, case, ensure)

    # Continuous-journey moment (D5): once after a terminal audit, the "what I keep doing for you"
    # beat (deadline watching, re-audit on new docs, the growing Record). Gated on the Record flag.
    if status in ("audit_complete", "audit_incomplete") and get_settings().enable_record_view:
        keep = orchestration_step("record_post_audit_keep_doing")
        await ensure("record_keep_doing", "system_message", {"text": keep, "tone": "neutral"}, keep)


# Plain-language rendering of the engine's difference_category for his
# {reconciliation_explanation} slot (§5.4 rung 0).
_RECONCILIATION_EXPLANATION = {
    "gross_vs_net": "one is the gross charge and the other is the net after your plan paid",
    "billed_vs_allowed": "one applies the billed amount and the other the allowed amount",
    "timing": "one of them is an older snapshot taken before this claim finished processing",
}


def _gap_text(plan) -> str | None:
    """The dollar spread for his {gap} — None when it can't be computed, which degrades."""
    vals = [f["value"] for f in plan.figures if isinstance(f.get("value"), (int, float))]
    if len(vals) < 2:
        return None
    return f"${max(vals) - min(vals):,.2f}"


async def _ensure_reconcile_state(session, conv, case, ensure) -> None:
    """Reconcile-first (§A2 state 3): surface a material accumulator conflict as a USER-FACING
    state. The ladder comes from agents.reconcile.plan_reconcile — a state machine, so the
    provider/plan rung cannot render while Tyndale still has an answer or a resolving question.
    """
    from app.agents.reconcile import plan_reconcile
    from app.db.models.findings import Finding

    finding = (
        await session.execute(
            select(Finding)
            .where(Finding.case_file_id == case.case_file_id)
            .where(Finding.category == "accumulator_discrepancy")
            .where(Finding.status == "open")
            .limit(1)
        )
    ).scalar_one_or_none()
    if finding is None:
        return

    plan = plan_reconcile(
        finding.facts or {},
        completeness_confirmed=bool((case.coverage or {}).get("eob_set_complete")),
    )
    _by_source = {f["source"]: f["value"] for f in plan.figures}
    explain = orchestration_step(
        "reconcile.explain",
        billed=_by_source.get("computed"),
        eob_owed=_by_source.get("eob_stated") or _by_source.get("coverage_stated"),
        # The engine's classified difference category IS his {reconciliation_explanation};
        # 'unexplained' passes None so the string degrades rather than asserting a cause.
        reconciliation_explanation=(
            _RECONCILIATION_EXPLANATION.get(plan.category) if plan.category != "unexplained" else None
        ),
    )
    await ensure(
        "reconcile",
        "system_message",
        {
            "text": explain,
            "tone": "neutral",
            "reconcile": {
                "category": plan.category,
                "figures": plan.figures,
                "computed_value": plan.computed_value,
                "confidence": plan.confidence,
                "rungs": plan.rungs,
            },
        },
        explain,
    )
    if plan.ask_input:
        ask = orchestration_step("reconcile.ask_one_input", doc_needed=plan.ask_input)
        await ensure(
            "reconcile_ask", "system_message",
            {"text": ask, "tone": "neutral", "branch_state": "reconcile"}, ask,
        )
    if plan.last_resort:
        last = orchestration_step(
            "reconcile.last_resort",
            gap=_gap_text(plan),
            provider=case.provider_name,
            payer=_payer_of(case),
        )
        await ensure(
            "reconcile_last", "system_message",
            {"text": last, "tone": "neutral", "branch_state": "reconcile"}, last,
        )


# Plain-English names for the cost-share inputs an X3 qualifier may cite ([A]-tier data
# labels, not authored voice — like the dollar figures themselves).
_X3_INPUT_NAMES = {
    "deductible_amount": "deductible",
    "oop_max_amount": "out-of-pocket maximum",
    "coinsurance_percent": "coinsurance rate",
}


def _x3_qualifier(a, disclosure) -> dict | None:
    """The X3 qualifier for the tyndale_computed figure — SAME visual unit as the number
    (the moment card renders it under the figure). Tier 0 forbids one (hedging a complete
    number is its own X3 failure); tier 1 gets the point form; tier ≥2 the range form when
    a range exists. Names the most material missing input (chase-worthy first)."""
    if disclosure is None or disclosure.tier == 0 or not disclosure.missing_inputs:
        return None
    named_key = (disclosure.chase_inputs or disclosure.missing_inputs)[0]
    name = _X3_INPUT_NAMES.get(named_key, named_key.replace("_", " "))
    has_range = (
        a.tyndale_computed_low is not None
        and a.tyndale_computed_high is not None
        and a.tyndale_computed_low != a.tyndale_computed_high
    )
    if disclosure.tier >= 2 and has_range:
        return {
            "text": (
                f"between ${a.tyndale_computed_low:,.2f} and ${a.tyndale_computed_high:,.2f} "
                f"until I see your {name}"
            ),
            "names": [name],
            "form": "range",
            "same_unit": True,
        }
    return {
        "text": f"based on a typical {name} — your plan's SBC would pin it down",
        "names": [name],
        "form": "point",
        "same_unit": True,
    }


async def _ensure_three_number_moment(session, conv, case, ensure) -> None:
    from app.agents.orchestrator import _assemble_result  # lazy — avoids the import cycle

    result = await _assemble_result(str(case.case_file_id), composed="")
    a = result.audit
    if a is None:
        return
    # Rung-2 completions may lack an anchor a document never stated (bill-only: no EOB
    # figure; EOB-only: billed comes from the EOB). None renders as an honest em dash in
    # the headline; the card gets the raw None and shows its own "not on file" treatment.
    eob_known = a.eob_member_responsibility is not None
    delta = round(a.eob_member_responsibility - a.tyndale_computed, 2) if eob_known else None
    has_range = a.tyndale_computed_low is not None and a.tyndale_computed_high is not None and (
        a.tyndale_computed_low != a.tyndale_computed_high
    )
    tyndale_str = (
        f"between ${a.tyndale_computed_low:,.2f} and ${a.tyndale_computed_high:,.2f}"
        if has_range
        else f"${a.tyndale_computed:,.2f}"
    )
    headline = orchestration_step(
        "three_number_reveal",
        billed=f"${a.provider_billed:,.2f}" if a.provider_billed is not None else "—",
        payer=_payer_of(case),
        eob_owed=f"${a.eob_member_responsibility:,.2f}" if eob_known else "—",
        tyndale_owed=tyndale_str,
    )
    # E3 — the gap framing. None on a clean bill (gap 0), a negative gap, or an unknown EOB
    # number; the moment then renders the numbers with no callout rather than "$0.00 less".
    from app.agents.grounding import gap_callout

    qualifier = _x3_qualifier(a, result.disclosure)
    # L2 (round-2) — the service-context line: provider · payer from TYPED fields only.
    # Parts we don't know are dropped; both unknown -> no key, and the card renders no line.
    context = " · ".join(x for x in (case.provider_name, _payer_of(case)) if x)
    await ensure(
        "moment:three_number", "moment_card",
        {"variant": "three_number", **({"context": context} if context else {}),
         "provider_billed": a.provider_billed,
         "eob_member_responsibility": a.eob_member_responsibility,
         "tyndale_computed": a.tyndale_computed,
         **(
             {"tyndale_computed_low": a.tyndale_computed_low,
              "tyndale_computed_high": a.tyndale_computed_high}
             if has_range
             else {}
         ),
         **({"qualifier": qualifier} if qualifier else {}),
         "computed_source": a.computed_source,
         "delta": delta, "headline": headline,
         "gap_callout": (
             gap_callout(a.eob_member_responsibility, a.tyndale_computed) if eob_known else None
         )},
    )


async def _ensure_unlock_more(session, conv, case, ensure) -> None:
    """The unlock-more card on a COMPLETED audit with un-checked inputs: the same
    DocumentNeed items the needs-documents state uses, under copy that frames them as
    sharpening the finished audit rather than finishing it. Both keys are engineering
    placeholders pending Brock (asks §3.11) — a NEW voice state his script doesn't have."""
    from app.agents.orchestrator import _documents_needed  # lazy — avoids the import cycle

    needs = _documents_needed(case)
    if all(d.have for d in needs):
        return  # everything's on file — nothing to unlock
    intro = orchestration_step("unlock_more.intro")
    hint = orchestration_step("unlock_more.item_hint")
    await ensure(
        "unlock_more", "system_message",
        {"text": intro, "tone": "neutral",
         "unlock_more": {
             "intro": intro, "item_hint": hint,
             "items": [
                 {"key": d.key, "label": d.label, "how_to_get": d.how_to_get, "have": d.have}
                 for d in needs
             ],
         }},
        intro,
    )


async def _ensure_needs_documents(session, conv, case, ensure) -> None:
    from app.agents.orchestrator import _documents_needed  # lazy — avoids the import cycle

    items = [
        {"key": d.key, "label": d.label, "how_to_get": d.how_to_get, "have": d.have}
        for d in _documents_needed(case)
    ]
    intro = orchestration_step("needs_documents_intro")  # §8.1 (no variables)
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
        # Continuous-journey (D5): at the user's FIRST-ever upload, frame this as the start of their
        # file. Idempotent (marker) + gated on the Record flag.
        if get_settings().enable_record_view:
            total = (
                await session.execute(
                    select(func.count()).select_from(CaseFile)
                    .where(CaseFile.user_id == case.user_id)
                    .where(CaseFile.soft_deleted_at.is_(None))
                )
            ).scalar_one()
            if total <= 1 and "record_first_upload" not in await _markers(session, conv.conversation_id):
                frame = orchestration_step("record_first_upload_frame")
                await _insert(
                    session, conv, "system_message",
                    {"text": frame, "tone": "neutral", "marker": "record_first_upload"}, frame,
                )
        await session.commit()
        return str(conv.conversation_id)


# --- verify-text writers (D4b, Phase B) — a free-text reply produces a SUGGESTION, never a
# confirmation (the tap commits). None of these touch case.encounter_confirmations or the status.
async def _post(
    case_file_id: str, *, role: str, kind: str, payload: dict | None = None, content: str | None = None
) -> str | None:
    """Post one thread entry. When `payload` carries a `marker`, this is IDEMPOTENT.

    The marker check used to live only in `_reconcile`, so every caller that posted directly
    through here — `post_not_sure_acknowledgment` among them — claimed idempotency it didn't
    have (deep review, finding 7). Two layers now hold it: this read-then-skip for the ordinary
    case, and a partial unique index (migration 0039) for the concurrent one, because
    check-then-insert races by construction.
    """
    marker = (payload or {}).get("marker")
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
        # Read the id up front: a rollback below EXPIRES `conv`, and touching an expired
        # attribute afterwards triggers a lazy refresh — IO outside the greenlet context, which
        # surfaces as MissingGreenlet rather than as the conflict we actually handled.
        conversation_id = str(conv.conversation_id)
        if marker and marker in await _markers(session, conv.conversation_id):
            return conversation_id  # already said; saying it twice is the bug
        try:
            # Both inside the guard: _insert flushes, so a marker collision surfaces THERE,
            # not at commit. Catching only the commit left the exception escaping into the
            # caller's blanket except — visible as "the bridge failed" rather than as what it
            # actually is.
            await _insert(session, conv, kind, payload, content=content, role=role)
            await session.commit()
        except IntegrityError:
            # The race the index exists to catch: another writer inserted the same marker
            # between our check and our commit. The thread is already correct — one entry,
            # theirs — so this is a no-op, but it is COUNTED rather than swallowed, because
            # "self-healing and unmeasured" is how a losing reconcile stays invisible.
            await session.rollback()
            BRIDGE_CONFLICTS[str(marker)] += 1
            log.info("bridge_marker_conflict", case_file_id=case_file_id, marker=marker)
        return conversation_id


async def post_user_utterance(case_file_id: str, text: str) -> str | None:
    """Persist the user's free-text verification reply as a user thread message."""
    return await _post(case_file_id, role="user", kind="message", content=text)


def _intended_answer(mappings: list[dict]) -> str | None:
    """The single answer the user intended across the mapped cards ({their_answer}, §4.3), or
    None when they disagree — None degrades rather than asserting one of them."""
    answers = {str(m.get("answer")) for m in (mappings or []) if m.get("answer")}
    return answers.pop() if len(answers) == 1 else None


async def post_verification_suggestion(
    case_file_id: str, mappings: list[dict], summary: str
) -> str | None:
    """A pre-selectable suggestion (mapped cards + one confirm prompt). NOT a confirmation."""
    text = orchestration_step(
        "verification_map_confirm", line_desc=summary, their_answer=_intended_answer(mappings)
    )
    return await _post(
        case_file_id, role="system", kind="verification_suggestion",
        payload={"text": text, "summary": summary, "mappings": mappings}, content=text,
    )


async def post_not_sure_acknowledgment(case_file_id: str) -> str | None:
    """§4.4 (D8) — "not sure" is an honest answer and must be SEEN to be honoured.

    The engine already audits around an unsure line item; this is the missing user-facing half:
    the thread says so plainly instead of leaving the user to wonder whether they broke
    something. Idempotent like every bridge entry (one per case)."""
    text = orchestration_step("verification_not_sure")
    return await _post(
        case_file_id, role="system", kind="system_message",
        payload={"text": text, "tone": "neutral", "marker": "not_sure_ack"}, content=text,
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
