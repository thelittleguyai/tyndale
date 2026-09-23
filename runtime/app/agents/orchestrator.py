"""run_audit — sequences Bill Detective → Math Person → Lead Planner per
V1-Lite collapsed effort scaling (2 subagents for "bill check with finding"),
then assembles the API ``AuditResult`` from the persisted findings.

Falls back to the MRI fixture when:
  * ``settings.use_real_claude`` is False, OR
  * ``settings.use_real_claude`` is True BUT ``anthropic_api_key`` is unset
    AND ``settings.allow_fixture_fallback`` is True.

In production, ``allow_fixture_fallback`` should be False so missing creds
raise loudly at audit time.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import structlog
from sqlalchemy import bindparam, cast, func, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB

from app.agents import bill_detective, lead_planner, math_person
from app.agents.audit_budget import AuditBudget, reset_audit_budget, set_audit_budget
from app.agents.context_loader import orchestration_step
from app.agents.llm_health import claude_path_label, record_audit_run, record_system_alert
from app.agents.grounding import finding_source_line
from app.agents.wrongdoc import classify_wrong_document
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.schemas.case_file import (
    AuditProvenance,
    AuditResult,
    Citation,
    Disclosure,
    DocumentNeed,
    FindingOut,
    ThreeNumberAudit,
    as_dict,
)
from app.schemas.encounter import (
    DEFAULT_INTRO_MESSAGE,
    ConfirmationsAccepted,
    DocumentExtraction,
    ExtractResult,
    LineItem,
    LineItemConfirmation,
)
from app.agents.example_scenarios import backfill_scenarios
from app.sources import benefits_context
from app.sources.case_data import load_case_eobs_coverage
from app.sources.materiality import (
    DISCLOSURE_TIER_LABELS,
    USER_CHASE,
    disclosure_tier,
    is_material,
)
from app.sources.missing_data_priors import MISSING_DATA_PRIORS, missing_cost_share_inputs
from app.stubs.fixtures import mri_audit_fixture

log = structlog.get_logger(__name__)


async def _append_tripwire(
    case_file_id: str,
    kind: str,
    *,
    codes: list[str] | None = None,
    category: str | None = None,
    session=None,
) -> None:
    """Record that a fabrication guard fired on this case (Human Review Phase 1: the guards used
    to only LOG, so nothing per case said "a canary fired here"; the review queue's canary
    trigger reads these). ``kind``: grounding_drop | grounding_scrub | translate_drop |
    grounding_summary_regen | grounding_summary_degraded.

    Appends a typed entry to research_log with ONE atomic UPDATE —
    `research_log = coalesce(research_log, '[]') || :entry` — no read-modify-write, so a
    concurrent append is never lost, and no loaded ORM object is needed (the summary seams
    run after the session that loaded the case has closed). Joins ``session``'s transaction
    when given, else opens its own. Never raises: a tripwire that can't be recorded must not
    fail the audit it is describing."""
    entry = {
        "kind": "tripwire",
        "which": kind,
        "codes": list(codes or []),
        "category": category,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    stmt = (
        update(CaseFile)
        .where(CaseFile.case_file_id == UUID(case_file_id))
        .values(
            research_log=func.coalesce(CaseFile.research_log, cast(literal("[]"), JSONB)).op("||")(
                bindparam("tripwire_entry", value=[entry], type_=JSONB)
            )
        )
    )
    try:
        if session is not None:
            await session.execute(stmt)
            return
        async with AsyncSessionLocal() as s:
            await s.execute(stmt)
            await s.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "orchestrator.tripwire_append_failed", case_file_id=case_file_id, which=kind, error=str(exc)
        )


# The canary set the fixtures plant (intelligence-layer/prompts/README.md); a guard that fires
# on one of THESE caught a marker leaking — every other guard fire is a plain guard drop.
CANARY_MARKERS = frozenset({"02417", "05821", "Z4411"})
GUARD_DROP_KINDS = frozenset({
    "grounding_drop", "translate_drop", "grounding_summary_regen", "grounding_summary_degraded",
    "legal_claim_downgraded",
})


def canary_marker_entries(case) -> list[dict]:
    """M6 (e2e 2026-09-23): tripwires that caught a PLANTED fixture marker — the meaning
    "canary" always had. A guard firing on a legitimate-but-ungrounded code is not one."""
    return [
        e for e in tripwire_entries(case)
        if any(str(c).upper() in CANARY_MARKERS for c in (e.get("codes") or []))
    ]


def guard_drop_entries(case) -> list[dict]:
    """Tripwires where a fabrication guard REMOVED or downgraded something (drop / regen /
    degrade / downgrade) — scrubs excluded, marker hits included."""
    return [e for e in tripwire_entries(case) if e.get("which") in GUARD_DROP_KINDS]


def tripwire_entries(case) -> list[dict]:
    """The case's tripwire records (see _append_tripwire); [] when none fired."""
    return [
        e for e in (getattr(case, "research_log", None) or [])
        if isinstance(e, dict) and e.get("kind") == "tripwire"
    ]


async def _set_status(
    case_file_id: str,
    status: str,
    *,
    incomplete_reason: str | None = None,
    expected_status: str | None = None,
    expected_reconcile_token: UUID | None = None,
) -> bool:
    """Set the case status and, atomically, its audit_incomplete_reason. The reason is always
    written (default None), so any non-incomplete transition (audit_running, audit_complete, a
    re-audit) clears a stale reason — only an audit_incomplete transition carries one.

    Returns True when the transition was applied. Every ordinary caller is UNCONDITIONAL (the
    owner of a run is entitled to its own terminal write). ``expected_status`` — and, for the
    stranded-audit healer, ``expected_reconcile_token`` — turn the write into a compare-and-swap
    under a row lock: if the case has moved on (a live replica finished the audit between the
    healer's claim and this follow-up), NOTHING is written, no side effect fires, and the caller
    gets False (deep review C2 — the healer used to stomp audit_complete back to system_error)."""
    user_id = None
    was_system_error = False
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(
                select(CaseFile)
                .where(CaseFile.case_file_id == UUID(case_file_id))
                .with_for_update()
            )
        ).scalar_one_or_none()
        guarded = expected_status is not None or expected_reconcile_token is not None
        if cf is None and guarded:
            return False
        if cf is not None:
            if expected_status is not None and cf.status != expected_status:
                log.warning(
                    "orchestrator.set_status.refused",
                    case_file_id=case_file_id, wanted=status,
                    expected_status=expected_status, actual_status=cf.status,
                )
                return False
            if expected_reconcile_token is not None and cf.reconcile_token != expected_reconcile_token:
                log.warning(
                    "orchestrator.set_status.refused",
                    case_file_id=case_file_id, wanted=status, reason="reconcile_token_mismatch",
                )
                return False
            # §10.4's promise trigger: remember whether this case was sitting in the
            # system_error state BEFORE this transition overwrites it.
            was_system_error = (
                cf.status == "audit_incomplete" and cf.audit_incomplete_reason == "system_error"
            )
            cf.status = status
            cf.audit_incomplete_reason = incomplete_reason
            if status == "audit_running":
                # A fresh run: first heartbeat, and a clean slate for the healer.
                cf.audit_heartbeat_at = datetime.now(timezone.utc)
                cf.reconcile_attempts = 0
            if expected_reconcile_token is None:
                # An owner's own write voids any healer claim on the row (the healer's later
                # CAS then fails on the token as well as the status). The healer's guarded
                # write KEEPS its token until its side effects are done — that is what makes a
                # heal that died mid-way re-pickable.
                cf.reconcile_token = None
                cf.reconcile_claimed_at = None
            user_id = cf.user_id
            await s.commit()
    await _status_side_effects(case_file_id, status, incomplete_reason, user_id, was_system_error)
    return True


async def _heartbeat(case_file_id: str) -> None:
    """Bump the running audit's heartbeat (phase boundaries). One tiny UPDATE, only while the
    case is still audit_running; updated_at is deliberately left alone. Never raises — a missed
    beat must not fail an audit (the threshold is 3x the budget for exactly that reason)."""
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(CaseFile)
                .where(
                    CaseFile.case_file_id == UUID(case_file_id),
                    CaseFile.status == "audit_running",
                )
                .values(
                    audit_heartbeat_at=datetime.now(timezone.utc),
                    updated_at=CaseFile.updated_at,
                )
            )
            await s.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("orchestrator.heartbeat.failed", case_file_id=case_file_id, error=str(exc))


async def _status_side_effects(
    case_file_id: str,
    status: str,
    incomplete_reason: str | None,
    user_id,
    was_system_error: bool,
    *,
    skip_review_enqueue: bool = False,
) -> None:
    """Everything that follows a committed status transition — the thread projection, the
    lifecycle event, the review-queue offer, the emails. Split from _set_status so the healer
    can REPLAY them for a row whose previous heal died after the flip (every step is
    idempotent; ``skip_review_enqueue`` is for a replay that finds the run already enqueued)."""
    # Chat-first event bridge (DL-91) — render the transition into the case thread. Flag-gated +
    # error-swallowing inside; a no-op when ENABLE_CHAT_FIRST_AUDIT is off. Lazy import (the bridge
    # is hooked from here, so it must not be imported at module load).
    from app.agents import thread_bridge

    await thread_bridge.bridge_case_state(case_file_id)
    # Internal analytics (P0): the audit-lifecycle funnel is server-known — emit it from this one
    # chokepoint. Best-effort + lazy-imported; terminal transitions are idempotent per case so a
    # reconciliation re-run can't double-count.
    if user_id is not None:
        await _emit_lifecycle_event(case_file_id, status, incomplete_reason, user_id)
    # Human Review Phase 1 (doc 39 §7-2d): every terminal run is offered to the reviewer queue
    # from this same chokepoint. Policy + triggers live in app.review.queue; it never raises.
    if status in ("audit_complete", "audit_incomplete") and not skip_review_enqueue:
        from app.review import queue as review_queue

        await review_queue.on_terminal(case_file_id, status, incomplete_reason)
    # The audit-ready email (D3) — §2.2's "I'll email you the moment it's ready", kept from the
    # same chokepoint that owns terminal status. Flag-gated, once-per-case and self-no-op'ing
    # inside; a send failure must never fail the audit that just succeeded, so it's swallowed
    # here the same way the thread bridge is.
    from app.notify.audit_ready import should_send

    if should_send(status, incomplete_reason):
        try:
            from app.notify.audit_ready import send_audit_ready_email

            await send_audit_ready_email(case_file_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("notify.audit_ready.failed", case_file_id=case_file_id, error=str(exc))
    # §10.4 — "I'll email you the moment I've got it working again." True only if we send it:
    # a case that sat in system_error and has now genuinely completed gets the recovery notice.
    if was_system_error and status == "audit_complete":
        try:
            from app.notify.audit_ready import send_recovery_email

            await send_recovery_email(case_file_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("notify.recovery.failed", case_file_id=case_file_id, error=str(exc))


async def _emit_lifecycle_event(case_file_id, status, incomplete_reason, user_id) -> None:
    from app.analytics.emit import emit, emit_idempotent

    if status == "audit_running":
        await emit("audit_started", user_id=user_id, case_file_id=UUID(case_file_id))
        return
    terminal = None
    if status == "audit_complete":
        terminal = "audit_completed"
    elif status == "audit_incomplete":
        terminal = "audit_system_error" if incomplete_reason == "system_error" else "audit_needs_documents"
    if terminal is not None:
        await emit_idempotent(
            terminal, dedupe_key=f"{terminal}:{case_file_id}", user_id=user_id,
            case_file_id=UUID(case_file_id),
        )
    if terminal == "audit_needs_documents":
        # Close-the-loop (flagship): the request is issued now; upload emits _satisfied on return.
        await emit_idempotent(
            "document_request_issued", dedupe_key=f"document_request_issued:{case_file_id}",
            user_id=user_id, case_file_id=UUID(case_file_id),
        )


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


async def _run_real_agents(
    case_file_id: str,
    accumulator: dict | None,
    confirmations: list[dict],
    budget: AuditBudget,
) -> tuple[str, bool, dict]:
    """Bill Detective ∥ Math Person, then Lead Planner, under the audit budget (Item 1).

    Latency (Item 2): per DL-80 Math Person consumes the PRE-COMPUTED accumulator (injected
    context), NOT Bill Detective's output — so BD and MP are independent and run CONCURRENTLY,
    cutting the critical path from BD+MP+LP to max(BD,MP)+LP (measured ~273s→~195s on case
    e539735e, where BD alone was 143s). Each agent runs on its OWN session for the HIPAA
    hook-audit rows — tools already open their own sessions for finding writes, so the passed
    session only ever carried the tool-invocation trail — meaning the concurrent runs never share
    a session. Lead Planner composes from both; if the budget is spent by then it is skipped at
    that safe boundary — the three-number finding Math Person wrote survives the cutoff. Returns
    (composed_summary, budget_stopped, stage_ms)."""
    stage_ms: dict[str, int] = {}

    async def _bill_detective():
        t = time.monotonic()
        async with AsyncSessionLocal() as s:
            r = await bill_detective.run(
                case_file_id, mode="diagnose", confirmations=confirmations, session=s
            )
            await s.commit()
        return r, _ms(t)

    async def _math_person():
        t = time.monotonic()
        async with AsyncSessionLocal() as s:
            r = await math_person.run(case_file_id, accumulator=accumulator, session=s)
            await s.commit()
        return r, _ms(t)

    # BD and MP are independent — run them at the same time. gather propagates the first error and
    # cancels the sibling (a stage failure still fails the audit, as before). The budget contextvar
    # is copied into both tasks, so the regen short-circuit still governs each.
    wall = time.monotonic()
    (bd, bd_ms), (mp, mp_ms) = await asyncio.gather(_bill_detective(), _math_person())
    stage_ms["bill_detective_ms"] = bd_ms
    stage_ms["math_person_ms"] = mp_ms
    stage_ms["agents_parallel_wall_ms"] = _ms(wall)  # ≈ max(bd,mp) — the concurrency saving
    await _heartbeat(case_file_id)  # phase boundary: agents done
    budget_stopped = bd.budget_stopped or mp.budget_stopped
    log.info(
        "orchestrator.bill_detective.done",
        case_file_id=case_file_id, tool_calls=len(bd.tool_calls), usage=bd.usage,
    )
    log.info(
        "orchestrator.math_person.done",
        case_file_id=case_file_id, tool_calls=len(mp.tool_calls), usage=mp.usage,
    )

    composed = ""
    if budget.expired():
        log.warning("orchestrator.budget.skipped_agent", case_file_id=case_file_id, stage="lead_planner")
        budget_stopped = True
    else:
        t = time.monotonic()
        async with AsyncSessionLocal() as s:
            lp = await lead_planner.compose_final(
                case_file_id, bd.final_text, mp.final_text, session=s
            )
            await s.commit()
        stage_ms["lead_planner_ms"] = _ms(t)
        await _heartbeat(case_file_id)  # phase boundary: summary composed
        composed = lp.final_text
        budget_stopped = budget_stopped or lp.budget_stopped
        log.info(
            "orchestrator.lead_planner.done",
            case_file_id=case_file_id, tool_calls=len(lp.tool_calls), usage=lp.usage,
            stop_action=lp.stop_action, human_review_needed=lp.human_review_needed,
        )

    # Prose grounding (2026-08-18): findings and the summary are scanned against the
    # documents' own text before ANY terminal state — the same fabrication class the
    # translate guard stops, one layer up.
    t = time.monotonic()
    composed = await _ground_prose(case_file_id, composed, budget, bd.final_text, mp.final_text)
    stage_ms["prose_grounding_ms"] = _ms(t)
    await _heartbeat(case_file_id)  # phase boundary: grounding done

    # Retrieval grounding (e2e 2026-09-23 B1): what this run actually retrieved is recorded
    # on the case, and a legal claim that no retrieved chunk backs is downgraded before any
    # terminal state — never a [B] claim with an empty rulebook behind it.
    all_calls = list(bd.tool_calls) + list(mp.tool_calls) + (list(lp.tool_calls) if composed else [])
    await _ground_retrieval(case_file_id, all_calls)

    return composed, budget_stopped, stage_ms


async def _ground_retrieval(case_file_id: str, tool_calls: list[dict]) -> None:
    from app.agents import retrieval_grounding as rg

    record = rg.retrieval_record(tool_calls)
    await rg.record_retrieval_on_case(case_file_id, record)
    if record["status"] != "ok":
        log.warning(
            "orchestrator.retrieval_" + record["status"], case_file_id=case_file_id,
            calls=record["calls"], errors=record["errors"], chunks=record["chunks"],
            reasons=record["error_reasons"],
        )
    downgraded = await rg.ground_legal_claims(case_file_id, rg.knowledge_chunks(tool_calls))
    for category in downgraded:
        await _append_tripwire(case_file_id, "legal_claim_downgraded", category=category)


async def _finalize_result(
    case_file_id: str,
    composed: str,
    budget: AuditBudget,
    budget_stopped: bool,
    started: float,
    stage_ms: dict,
    path: str,
    *,
    manage_status: bool,
) -> AuditResult:
    """Assemble the result, pick the terminal status + reason (budget_exceeded overrides a
    three-number result — the summary couldn't finish), persist the status (finalize path
    only), and record the run's timing/regens for the admin System page."""
    result = await _assemble_result(case_file_id, composed)
    # Persist the (grounded) summary BEFORE the status transition: the thread projection fired
    # by _set_status, the user's later GET /v1/audit and the reviewer's Analysis tab all assemble
    # with composed="" and used to show NOTHING the user had read (deep review). Always written,
    # so a re-run whose summary degraded to "" replaces the previous run's text instead of
    # resurrecting it.
    await _persist_summary(case_file_id, composed)
    # Terminal state + honest reason. Three real numbers = a COMPLETE audit even if the budget cut
    # the prose summary short (the numbers + findings still ship — a degraded summary, not a
    # failure). A run cut short with NO numbers is a system_error; agents that ran clean but
    # couldn't compute the numbers because inputs are missing is the user-actionable
    # needs_documents state — the wrong-framing bug this fixes (2026-07-07).
    if result.audit is not None:
        # Complete — keep _assemble_result's "complete" AuditResult status (the API contract); the
        # PERSISTED case status is audit_complete. incomplete_reason/documents_needed are already
        # clean from _assemble_result.
        terminal, reason = "audit_complete", None
    else:
        terminal = "audit_incomplete"
        reason = "system_error" if (budget.expired() or budget_stopped) else "needs_documents"
        # _assemble_result ran BEFORE the reason was persisted (it defaults audit-None to
        # needs_documents + a checklist) — override with the computed reason, and clear the
        # checklist unless this really is needs_documents.
        result = result.model_copy(
            update={
                "status": "audit_incomplete",
                "incomplete_reason": reason,
                "documents_needed": (
                    await _documents_needed_with_plan(case_file_id)
                    if reason == "needs_documents"
                    else []
                ),
            }
        )

    if manage_status:
        await _set_status(case_file_id, terminal, incomplete_reason=reason)
    if reason == "system_error":
        # The ONLY terminal path that tells the user "our team has been notified" — make it true:
        # a structured alert the admin System page counts.
        record_system_alert()
        log.error(
            "audit.system_error",
            case_file_id=case_file_id, terminal=terminal, budget_stopped=budget_stopped,
        )
    duration = round(time.monotonic() - started, 2)
    record_audit_run(
        duration_seconds=duration, reason=reason or "complete",
        regens=budget.regens_used, path=path, stage_ms=stage_ms,
    )
    log.info(
        "orchestrator.audit.done",
        case_file_id=case_file_id, duration_s=duration, terminal=terminal,
        reason=reason, regens=budget.regens_used, **stage_ms,
    )
    # Internal analytics (P0, §5 ops): the audit flow-stage latency. Best-effort; one load for uid.
    from app.analytics.emit import emit

    _cf = await _load_case(case_file_id)
    if _cf is not None:
        await emit(
            "stage_completed", user_id=_cf.user_id, case_file_id=UUID(case_file_id),
            properties={"stage": "audit", "duration_ms": duration * 1000.0},
        )
    return result


async def _persist_summary(case_file_id: str, composed: str) -> None:
    """Best-effort: a summary that can't be stored must not fail the audit that produced it."""
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(CaseFile)
                .where(CaseFile.case_file_id == UUID(case_file_id))
                .values(audit_summary=composed or "")
            )
            await s.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("orchestrator.summary_persist_failed", case_file_id=case_file_id, error=str(exc))


def _new_audit_budget(settings) -> tuple[AuditBudget, float]:
    started = time.monotonic()
    return (
        AuditBudget(
            deadline=started + settings.audit_wall_clock_budget_seconds,
            regen_remaining=settings.audit_max_regenerations,
        ),
        started,
    )


def _has_real_anthropic_creds(settings) -> bool:
    """Real key must look like sk-ant-... — placeholder strings ('<from
    terraform output>', empty, unset) fall back to fixture instead of
    hitting Anthropic with an invalid key. Under Foundry (CO-18) the managed
    identity IS the credential, so no API key is required."""
    if settings.use_foundry and settings.foundry_endpoint:
        return True
    key = (settings.anthropic_api_key or "").strip()
    if not key:
        return False
    if key.startswith("<"):
        return False  # literal placeholder
    if not key.startswith("sk-"):
        return False  # not Anthropic-shaped
    return True


async def _run_accumulator_cross_check(case_file_id: str) -> dict | None:
    """CO-12B wiring — deterministic accumulator reconstruction + three-way
    cross-validation (DL-72) during the audit run. ``BenefitsContext.get_accumulator``
    computes the authoritative reconstruction from the uploaded EOBs, cross-validates
    it against the EOB-stated YTD + the card/user-stated coverage 'met' values, and
    (via its idempotent default writer) persists at most ONE open
    ``accumulator_discrepancy`` Finding on material disagreement.

    Returns a compact context dict for Math Person (computed figures + confidence +
    recorded assumptions), or None when skipped/failed.

    Guards:
      * Cases with NO uploaded EOB data are skipped — an all-zero reconstruction
        would spuriously "disagree" with card-stated met values the engine had no
        data to corroborate.
      * NEVER fails the audit: any error is logged and swallowed (Graceful
        Degradation Doctrine) — the agents still run without the pre-computed
        accumulator.
    """
    try:
        eobs, _coverage = await load_case_eobs_coverage(case_file_id)
        if not eobs:
            log.info("orchestrator.accumulator.skipped_no_eobs", case_file_id=case_file_id)
            return None
        as_of = date.today()
        result = await benefits_context.get_accumulator(case_file_id, as_of)
        log.info(
            "orchestrator.accumulator.done",
            case_file_id=case_file_id,
            deductible_applied=result.data.get("deductible_applied"),
            oop_applied=result.data.get("oop_applied"),
            eobs_counted=result.data.get("eobs_counted"),
            confidence=result.provenance.confidence,
        )
        assumptions = list(result.provenance.assumptions)
        # Disclosure tier (Sprint C, DL-85) threaded into Math Person's context so the
        # model reads the DETERMINISTIC confidence rather than picking its own.
        cv_material = any("disagree materially" in a for a in assumptions)
        disclosure = _compute_disclosure(_coverage, cross_validation_material=cv_material)
        return {
            "as_of": as_of.isoformat(),
            **result.data,
            "confidence": result.provenance.confidence,
            "assumptions": assumptions,
            "disclosure_tier": disclosure.tier,
            "disclosure_label": disclosure.label,
            "chase_inputs": disclosure.chase_inputs,
        }
    except Exception as exc:  # noqa: BLE001 — accumulator must never fail an audit
        log.warning(
            "orchestrator.accumulator.failed",
            case_file_id=case_file_id,
            error=str(exc),
        )
        return None


async def run_audit(case_file_id: str) -> AuditResult:
    settings = get_settings()

    # Fixture short-circuit -----------------------------------------------------
    if not settings.use_real_claude:
        log.info(
            "orchestrator.fixture_fallback",
            reason="USE_REAL_CLAUDE=false",
            case_file_id=case_file_id,
        )
        return mri_audit_fixture(case_file_id)
    if not _has_real_anthropic_creds(settings) and not settings.litellm_proxy_url:
        if settings.allow_fixture_fallback:
            log.warning(
                "orchestrator.fixture_fallback",
                reason="ANTHROPIC_API_KEY missing/placeholder and no LITELLM_PROXY_URL; allow_fixture_fallback=true",
                case_file_id=case_file_id,
            )
            return mri_audit_fixture(case_file_id)
        raise RuntimeError(
            "USE_REAL_CLAUDE=true but no real ANTHROPIC_API_KEY / LITELLM_PROXY_URL and "
            "ALLOW_FIXTURE_FALLBACK=false"
        )

    # Real agent run ------------------------------------------------------------
    # One audit session threads through the subagents so the PreToolUse /
    # PostToolUse hook writes (the HIPAA tool-invocation trail) persist; the
    # orchestrator commits once after the run (mirrors guard_send_email's
    # caller-commits split — CO-15).
    log.info("orchestrator.run_audit.start", case_file_id=case_file_id)

    # Item 1: run the agents under the wall-clock + regen budget. run_audit does NOT manage
    # case status (finalize_audit owns the audit_running→terminal state machine).
    budget, started = _new_audit_budget(settings)
    token = set_audit_budget(budget)
    try:
        # CO-12B: deterministic accumulator + cross-validation (pre-agent, survives regardless).
        accumulator = await _run_accumulator_cross_check(case_file_id)
        # Agents run concurrently on their own sessions (see _run_real_agents) — no shared session.
        composed, budget_stopped, stage_ms = await _run_real_agents(
            case_file_id, accumulator, [], budget
        )
        return await _finalize_result(
            case_file_id, composed, budget, budget_stopped, started, stage_ms,
            claude_path_label(settings), manage_status=False,
        )
    finally:
        reset_audit_budget(token)


def _compute_disclosure(coverage: dict | None, *, cross_validation_material: bool) -> Disclosure:
    """Deterministic disclosure tier (Sprint C, DL-85) from coverage completeness + the
    accumulator cross-validation verdict. The uncertainty proxy is the widest missing
    usd-prior span (how far the answer could swing); a missing input whose span crosses
    USER_CHASE becomes a document to chase (tier 3)."""
    missing = missing_cost_share_inputs(coverage)
    width, base = 0.0, 1.0
    for key in missing:
        prior = MISSING_DATA_PRIORS.get(key)
        if prior and prior.unit == "usd" and prior.usd_span() > width:
            width, base = prior.usd_span(), prior.high
    tier = disclosure_tier(
        width, base, missing_inputs=missing, cross_validation_material=cross_validation_material
    )
    chase = [
        key
        for key in missing
        if (p := MISSING_DATA_PRIORS.get(key)) and is_material(p.usd_span(), p.high, USER_CHASE)
    ]
    return Disclosure(
        tier=tier,
        label=DISCLOSURE_TIER_LABELS[tier],
        missing_inputs=missing,
        chase_inputs=chase,
    )


def _regime_provenance(
    case: CaseFile | None, profile_state: str | None = None
) -> AuditProvenance:
    """The coverage-regime context this audit ran under (Sprint B, DL-82). Every
    non-commercial or unconfirmed regime still uses the generic path but carries an
    explicit assumption naming the pending population corpus, so nothing silently
    pretends to have applied population-specific rules.

    ``profile_state`` (2026-08-19, settings item 2): feeds the jurisdiction assumption —
    document evidence wins over the profile default (app/sources/jurisdiction.py)."""
    from app.plan_types import COMMERCIAL_FAMILY, SUPPRESS_FEDERAL_PROTECTIONS

    regime = case.coverage_regime if case else None
    detection = (case.regime_detection if case else None) or {}
    verified = bool(detection.get("verified"))
    assumptions: list[str] = []
    if not regime:
        assumptions.append(
            "coverage regime not yet confirmed — audited under generic commercial rules (DL-82)"
        )
    elif regime not in COMMERCIAL_FAMILY:
        assumptions.append(
            f"audited under generic commercial rules — {regime} rules corpus pending (DL-82)"
        )
    # stldi / excepted benefits are OUTSIDE the No Surprises Act + ACA appeal rights — asserting
    # them would be a wrong answer (Brock 2026-07-06). Suppress + say so, not just tag a corpus.
    if regime in SUPPRESS_FEDERAL_PROTECTIONS:
        assumptions.append(
            f"'{regime}' is not qualifying health coverage — the No Surprises Act and ACA "
            "internal/external appeal rights DO NOT apply and are not asserted for this coverage"
        )
    elif not get_settings().enable_nsa_checks:
        assumptions.append(
            "surprise-billing / No Surprises Act checks are not yet enabled "
            "(pending the 50-state seed — DL-81/DL-88)"
        )
    # Jurisdiction (2026-08-19, settings item 2): named with its SOURCE so nothing pretends
    # state rules were applied before the seed. Document evidence wins over the profile.
    from app.sources.jurisdiction import case_jurisdiction

    state, source = case_jurisdiction(case, profile_state)
    if state:
        assumptions.append(
            f"state-law jurisdiction: {state} "
            f"({'from this case’s documents' if source == 'document' else 'from your profile'})"
            " — state-specific rules apply with the 50-state seed"
        )
    else:
        assumptions.append(
            "state-law jurisdiction unknown — set your state in Settings so state-specific "
            "rules can apply when the 50-state seed lands"
        )
    # Retrieval (e2e 2026-09-23 B1): the run's own record, named as an assumption so the
    # results page says it and the harness can assert it.
    from app.agents.retrieval_grounding import retrieval_entry

    entry = retrieval_entry(case) if case is not None else None
    retrieval = None
    if entry:
        retrieval = {k: entry.get(k) for k in ("status", "calls", "errors", "chunks", "error_reasons", "at")}
        if entry.get("status") == "unavailable":
            assumptions.append(
                "the rules corpus could not be reached during this audit — findings rest on "
                "your documents and the math; legal claims without a retrieved source were "
                "downgraded to 'worth checking'"
            )
        elif entry.get("status") == "degraded":
            assumptions.append(
                f"{entry.get('errors')} of {entry.get('calls')} rules lookups failed during this "
                "audit — a rule that lookup would have found may be missing"
            )
    return AuditProvenance(
        coverage_regime=regime, regime_verified=verified, assumptions=assumptions,
        retrieval=retrieval, retrieval_unavailable=bool(entry and entry.get("status") == "unavailable"),
    )


# Document-type families already present on a case (so we only ask for what's actually missing).
_EOB_FAMILY = {"eob", "ma_eob", "msn", "tricare_eob"}
_BILL_FAMILY = {"bill", "gfe", "itemized_bill"}


# Document types that satisfy the SBC/coverage-terms need (a benefits summary or the card).
_COVERAGE_FAMILY = {"plan_summary", "insurance_card"}


def _document_haystack(cf) -> str | None:
    """Every extracted document's stored OCR text, uppercased — the shared conviction
    corpus for the translate guard AND the prose-grounding pass. None when no full text is
    stored (legacy cases): no evidence, no conviction."""
    docs = [d for d in ((cf.documents if cf else None) or []) if isinstance(d, dict)]
    texts = [
        str(d.get("ocr_text") or "")
        for d in docs
        if (d.get("extraction_status") or "extracted") == "extracted" and d.get("ocr_text")
    ]
    return "\n".join(texts).upper() if texts else None


async def _ground_prose(
    case_file_id: str, composed: str, budget, bd_text: str, mp_text: str
) -> str:
    """The finding/summary grounding pass (2026-08-18, drop-if-basis / scrub-if-incidental).

    Runs after the agents, before any terminal state: findings whose BASIS depends on a
    code no document contains are DELETED (counted as grounding_drop:{category} alongside
    the doctrine violations on the ops panel); incidental parenthetical references are
    span-stripped; the LP summary gets ONE regeneration with the §3.10-style correction
    inline, then degrades to no-summary rather than shipping a fabricated code. Dropping
    to zero findings is safe by construction — the existing honest states (rung-2
    completion, all-clear, needs_documents) take over downstream."""
    from app.agents.context_loader import DOCTRINE_VIOLATIONS
    from app.sources import prose_grounding as pg

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        haystack = _document_haystack(case)
        if haystack is None:
            return composed  # legacy/preview-only case — no evidence, no conviction
        rows = (
            (await s.execute(select(Finding).where(Finding.case_file_id == UUID(case_file_id))))
            .scalars()
            .all()
        )
        vouched: set[str] = set()  # kept findings' reference codes vouch summary mentions
        dropped_codes: set[str] = set()
        kept: list = []
        for f in rows:
            verdict = pg.ground_finding(
                f.facts, f.legal_claim, f.recommendation, haystack, category=f.category
            )
            if verdict.action == "drop":
                DOCTRINE_VIOLATIONS[f"grounding_drop:{f.category}"] += 1
                log.error(
                    "orchestrator.grounding.finding_dropped",
                    case_file_id=case_file_id,
                    category=f.category,
                    ungrounded_codes=verdict.dropped_codes,
                )
                await _append_tripwire(
                    case_file_id, "grounding_drop", codes=verdict.dropped_codes,
                    category=f.category, session=s,
                )
                dropped_codes.update(verdict.dropped_codes)
                await s.delete(f)
            else:
                kept.append(f)
                # the SAME distinction the guard used: a kept finding's reference codes (the
                # correct code, the panel) vouch for the summary's mention of them
                _, refs = pg.code_sets(f.facts, f.legal_claim, f.recommendation, haystack, category=f.category)
                vouched |= refs
                if verdict.scrubbed:
                    DOCTRINE_VIOLATIONS[f"grounding_scrub:{f.category}"] += 1
                    await _append_tripwire(
                        case_file_id, "grounding_scrub", category=f.category, session=s
                    )
                    for name, payload in verdict.scrubbed.items():
                        setattr(f, name, payload)
                    log.warning(
                        "orchestrator.grounding.finding_scrubbed",
                        case_file_id=case_file_id,
                        category=f.category,
                    )
        if dropped_codes:
            # Consistency (e2e 2026-09-23 B2): a deadline whose dispute basis was the dropped
            # finding must not keep citing it while the reveal says "nothing hidden".
            await _reconcile_deadlines_after_drop(s, case_file_id, dropped_codes, kept)
        await s.commit()

    codes = pg.summary_ungrounded_codes(composed, haystack, vouched)
    if not codes:
        return composed
    if budget.take_regen():
        DOCTRINE_VIOLATIONS["grounding_summary_regen"] += 1
        log.warning(
            "orchestrator.grounding.summary_regenerating",
            case_file_id=case_file_id,
            ungrounded_codes=codes,
        )
        # The WORST fabrication seam — a code bad enough to throw the summary away — recorded
        # no tripwire, so the review queue's canary trigger never fired for it (deep review).
        await _append_tripwire(case_file_id, "grounding_summary_regen", codes=codes)
        async with AsyncSessionLocal() as s:
            lp = await lead_planner.compose_final(
                case_file_id, bd_text, mp_text, session=s,
                extra_instruction=pg.regeneration_instruction(codes),
            )
            await s.commit()
        composed = lp.final_text
        codes = pg.summary_ungrounded_codes(composed, haystack, vouched)
    if codes:
        # Regeneration unavailable or insufficient: no summary beats a fabricated code.
        DOCTRINE_VIOLATIONS["grounding_summary_degraded"] += 1
        log.error(
            "orchestrator.grounding.summary_degraded",
            case_file_id=case_file_id,
            ungrounded_codes=codes,
        )
        await _append_tripwire(case_file_id, "grounding_summary_degraded", codes=codes)
        return ""
    return composed


async def _reconcile_deadlines_after_drop(
    session, case_file_id: str, dropped_codes: set[str], survivors: list
) -> None:
    """The deadline's dispute basis is derived from SURVIVING findings only. A pending
    deadline whose agent-written description leans on a dropped code is re-described from
    what survived (their categories, humanized) — or, when nothing survived, left to its
    rule label (the appeal window is real; the basis the agent named was not)."""
    from app.db.models.deadlines import Deadline
    from app.sources.gameplan import humanize_category

    rows = (
        await session.execute(
            select(Deadline)
            .where(Deadline.case_file_id == UUID(case_file_id))
            .where(Deadline.status == "pending")
        )
    ).scalars().all()
    if not rows:
        return
    pattern = re.compile(r"(?<![A-Z0-9])(?:" + "|".join(re.escape(c) for c in sorted(dropped_codes)) + r")(?![A-Z0-9])")
    basis = [humanize_category(getattr(f, "category", "") or "") for f in survivors]
    basis = [b for b in basis if b]
    for d in rows:
        if not d.description or not pattern.search(d.description.upper()):
            continue
        before = d.description
        d.description = ("Dispute basis: " + "; ".join(dict.fromkeys(basis))) if basis else None
        log.warning(
            "orchestrator.deadline_basis_reconciled",
            case_file_id=case_file_id, deadline_type=d.deadline_type,
            dropped_codes=sorted(dropped_codes), survivors=len(basis), was=before[:120],
        )


def _rung2_three_numbers(case, plan_coverage: dict | None = None) -> dict | None:
    """Deterministic three-number completion from DOCUMENT-STATED money (the rung-2 engine).

    Anchors, in order of correctness: the EOB's allowed amount (the true cost-share base) →
    the EOB's billed → the itemized lines' billed total. Every figure here is a document
    fact or a bounded computation over one — nothing is invented; an anchor no document
    states stays None and the API says so. Returns None when NO anchor exists (no itemized
    detail and no EOB money) — the genuine needs_documents shape (the Beloit day-one case).

    ``plan_coverage`` (2026-08-19, settings item 5): terms extracted from the user's
    plan-level SBC. The case's own coverage wins field-by-field; the plan SBC fills the
    gaps — still document-stated terms, just stated once at the plan level.
    """
    if case is None:
        return None
    from app.sources.cost_share_model import rung2_range
    from app.sources.extraction import eob_money_figures
    from app.sources.plan_docs import merge_case_coverage

    lines_total: float | None = None
    items = [li for li in (case.line_items or []) if isinstance(li, dict)]
    billed_values = [li.get("billed_amount") for li in items if li.get("billed_amount") is not None]
    if billed_values:
        try:
            lines_total = round(sum(float(v) for v in billed_values), 2)
        except (TypeError, ValueError):
            lines_total = None

    eob_figs: dict[str, float | None] = {}
    for d in case.documents or []:
        if not isinstance(d, dict) or (d.get("document_type") not in _EOB_FAMILY):
            continue
        text = d.get("ocr_text") or d.get("ocr_text_preview") or ""
        if text:
            eob_figs = eob_money_figures(text)
            if any(v is not None for v in eob_figs.values()):
                break

    provider_billed = lines_total if lines_total is not None else eob_figs.get("billed_amount")
    eob_member = eob_figs.get("patient_responsibility")

    if eob_figs.get("allowed_amount") is not None:
        anchor, anchor_kind = eob_figs["allowed_amount"], "allowed"
    elif eob_figs.get("billed_amount") is not None:
        anchor, anchor_kind = eob_figs["billed_amount"], "billed"
    elif lines_total is not None:
        anchor, anchor_kind = lines_total, "billed"
    else:
        return None  # no document-stated money anywhere — the audit genuinely cannot stand

    rng = rung2_range(
        anchor, merge_case_coverage(case.coverage, plan_coverage), anchor_kind=anchor_kind
    )
    # Priors gate (Phil, 2026-08-18): while any prior the range consumed is still a
    # PLACEHOLDER, the user-visible range is suppressed — point form only. Brock's
    # researched table activates ranges per-entry by flipping the flag in the data.
    suppress = rng.placeholder_basis
    return {
        "provider_billed": provider_billed,
        "eob_member_responsibility": eob_member,
        "tyndale_computed": rng.base,
        "tyndale_computed_low": None if suppress else rng.low,
        "tyndale_computed_high": None if suppress else rng.high,
        "anchor_kind": rng.anchor_kind,
        "missing_inputs": rng.missing_inputs,
    }


def _documents_needed(case, *, plan_sbc: bool = False) -> list[DocumentNeed]:
    """The 'to finish your audit' checklist for a needs_documents case — the three canonical audit
    inputs, EACH with a `have` flag from the case's real document inventory. Returning the full set
    (not just the missing ones) lets the UI show a true checked/unchecked state and lets the user
    watch items flip to done as they upload. PHI-free: document types + plain 'how to get it'.

    ``plan_sbc`` (2026-08-19, settings item 5): the SBC describes the PLAN, not one bill — a
    plan-level SBC in the user's Plan documents home satisfies the SBC line on EVERY case, so
    callers pass what app.sources.plan_docs.plan_sbc_state found and this checklist never asks
    for a document the user already gave us once."""
    types = {
        (d or {}).get("document_type")
        for d in (getattr(case, "documents", None) or [])
        if isinstance(d, dict)
    }
    have_eob = bool(types & _EOB_FAMILY)
    have_bill = bool(types & _BILL_FAMILY)
    have_sbc = (
        plan_sbc or bool(getattr(case, "coverage", None)) or bool(types & _COVERAGE_FAMILY)
    )
    return [
        DocumentNeed(
            key="eob",
            label="Explanation of Benefits (EOB)",
            how_to_get=(
                "Your insurer posts this after they process a claim. Log in to your insurance "
                "portal, or call the member number on your card and ask them to send the EOB "
                "for this visit."
            ),
            have=have_eob,
        ),
        DocumentNeed(
            key="itemized_bill",
            label="Itemized bill",
            how_to_get=(
                "Call the provider's billing office (the number on your statement) and ask for "
                "an itemized bill — a detailed bill with the procedure (CPT) codes. They're "
                "required to provide one."
            ),
            have=have_bill,
        ),
        DocumentNeed(
            key="sbc",
            label="Summary of Benefits and Coverage (SBC)",
            how_to_get=(
                "Your plan's benefits summary — find it in your insurance portal under Plan "
                "Documents, or ask your HR or insurer for the SBC. Already have it? Add it "
                "once under Settings → Plan documents and every case can use it."
            ),
            have=have_sbc,
        ),
    ]


def documents_all_satisfied(case, *, plan_sbc: bool = False) -> bool:
    """True once the case has every canonical audit input — the trigger to re-run a
    needs_documents audit after the user adds the last missing document. ``plan_sbc``
    counts the user's plan-level SBC (Settings → Plan documents), same as the checklist."""
    return all(d.have for d in _documents_needed(case, plan_sbc=plan_sbc))


# Agents persist citations as free-form dicts (the pg_store_finding tool schema is an open object,
# so real-Claude citations vary in their keys). The strict Citation model must NEVER 500 the audit
# fetch on a shape it didn't expect — project defensively: normalize the common field aliases,
# synthesize a marker when absent, and drop a citation only when it carries nothing usable.
_CITATION_ALIASES: dict[str, tuple[str, ...]] = {
    "src_id": ("src_id", "source_id", "source", "src", "id"),
    "authority": ("authority", "title", "name", "source_title", "label"),
    "section": ("section", "sec", "pincite"),
    "marker": ("marker", "inline_marker", "citation", "text"),
}


def _project_citation(c: dict) -> Citation | None:
    def pick(field: str) -> str:
        for k in _CITATION_ALIASES[field]:
            v = c.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    authority, src_id = pick("authority"), pick("src_id")
    marker = pick("marker")
    if not marker and (authority or src_id):  # synthesize an inline marker when the agent omitted it
        marker = f"[{authority}{', ' if authority and src_id else ''}{src_id}]"
    if not (authority or src_id or marker):
        return None  # nothing usable — drop rather than render an empty citation
    try:
        return Citation(
            authority=authority, section=pick("section") or None, src_id=src_id, marker=marker
        )
    except Exception:  # noqa: BLE001 — a malformed agent citation must never 500 the audit fetch
        return None


def _project_citations(raw: object) -> list[Citation]:
    out: list[Citation] = []
    for c in raw or []:  # type: ignore[union-attr]
        if isinstance(c, dict):
            pc = _project_citation(c)
            if pc is not None:
                out.append(pc)
    return out


_MONEY_FACT_RE = re.compile(r"(-)?\s*\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*(?:usd)?", re.IGNORECASE)


def _coerce_money(value: object) -> float:
    """An agent-written money fact as a float. The schema asks for a number; agents sometimes
    write "$185.00" or "1,234.50" instead. That is a formatting slip, not a missing figure —
    and `float("$185.00")` turned a fully computed audit into `needs_documents` (dev, 2026-09-18
    and 2026-09-21: pb="$185.00", eob="$24.00", tc="$24.00"). Anything that is not
    unambiguously ONE amount (a range, "N/A", free text) still raises, and is still logged."""
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = _MONEY_FACT_RE.fullmatch(value.strip())
        if m:
            amount = float(m.group(2).replace(",", "") + (m.group(3) or ""))
            return -amount if m.group(1) else amount
    raise ValueError(f"not a single money amount: {value!r}")


async def _assemble_result(case_file_id: str, composed: str) -> AuditResult:
    """Read findings from Postgres and project to AuditResult shape."""
    async with AsyncSessionLocal() as s:
        rows = (
            (await s.execute(select(Finding).where(Finding.case_file_id == UUID(case_file_id))))
            .scalars()
            .all()
        )
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        profile_state = None
        plan_sbc, plan_cov = False, None
        if case is not None:
            from app.db.models.users import User
            from app.sources.plan_docs import plan_sbc_state

            profile_state = (
                await s.execute(select(User.state).where(User.user_id == case.user_id))
            ).scalar_one_or_none()
            # Plan-level SBC (settings item 5): satisfies the checklist line and
            # supplies rung-2 terms when this case has no coverage of its own.
            plan_sbc, plan_cov = await plan_sbc_state(s, case.user_id)
    if not composed and case is not None:
        # Any read after finalize: what the user was actually shown (see _persist_summary).
        composed = case.audit_summary or ""
    provenance = _regime_provenance(case, profile_state)
    # A persisted accumulator_discrepancy is the cross-validation material signal (DL-72).
    cv_material = any(getattr(f, "category", None) == "accumulator_discrepancy" for f in rows)
    from app.sources.plan_docs import merge_case_coverage

    disclosure = _compute_disclosure(
        merge_case_coverage(case.coverage if case else None, plan_cov),
        cross_validation_material=cv_material,
    )

    findings: list[FindingOut] = []
    three_numbers: dict | None = None
    for f in rows:
        # Same defensive-read rule as citations, one level up (2026-08-19 dev sweep: an
        # agent stored the literal STRING 'null' as a recommendation, and the strict
        # FindingOut 500'd the audit fetch — `or {}` doesn't save you from a truthy string).
        facts = as_dict(f.facts) or {}
        # Citations live inside legal_claim["citations"] (Finding has no
        # separate citations column — see app/tools/db_tools.py).
        raw_citations = []
        if isinstance(f.legal_claim, dict):
            raw_citations = f.legal_claim.get("citations") or []
        # Defensive projection — real-agent citation dicts vary in shape and must never 500 the
        # audit fetch (the live bug: a citation missing src_id/marker raised ValidationError here).
        citations = _project_citations(raw_citations)
        findings.append(
            _with_source_line(
                FindingOut(
                    finding_id=str(f.finding_id),
                    finding_type=f.finding_type,
                    category=f.category,
                    subagent_source=f.subagent_source or "unknown",
                    voice_tier=f.voice_tier or "B",
                    facts=facts,
                    legal_claim=as_dict(f.legal_claim),
                    recommendation=as_dict(f.recommendation),
                    citations=citations,
                )
            )
        )
        # The three-number audit lives in the first finding's facts that has
        # all three keys present AND numeric (typically Math Person's
        # payer-side finding). Defensive against an agent writing the keys
        # with None values when it couldn't extract one of the three.
        if three_numbers is None:
            pb = facts.get("provider_billed")
            eob = facts.get("eob_member_responsibility")
            tc = facts.get("tyndale_computed")
            if pb is not None and eob is not None and tc is not None:
                try:
                    three_numbers = {
                        "provider_billed": _coerce_money(pb),
                        "eob_member_responsibility": _coerce_money(eob),
                        "tyndale_computed": _coerce_money(tc),
                    }
                except (TypeError, ValueError):
                    log.warning(
                        "orchestrator.three_number_coercion_failed",
                        case_file_id=case_file_id,
                        finding_id=str(f.finding_id),
                        facts_subset={"pb": pb, "eob": eob, "tc": tc},
                    )

    if three_numbers is None:
        # Real agents ran but wrote no three-number finding — historically the SBC gate:
        # the Math Person (correctly) refuses to invent a member-responsibility figure
        # without coverage terms, and the whole audit parked in needs_documents. Phil's
        # ruling (2026-08-18, from the first full dev sweep): COMPLETE at the achievable
        # rung instead. The deterministic rung-2 engine anchors on document-stated money
        # (EOB allowed/billed, or the itemized lines) and sweeps the standard cost-share
        # model over the Sprint-C priors — the figure ships as a RANGE with an X3
        # qualifier, never as a refusal. NEVER {0,0,0}-as-complete (CO-15 T2.3): with no
        # document anchor at all, the honest needs_documents state below still applies.
        # Engage at audit time (status audit_running) and on reads of COMPLETED cases (the
        # rung-2 numbers are derived, not persisted — the bridge re-derives the moment after
        # finalize, deterministically reaching the same range). Never on a persisted
        # incomplete terminal: a legacy needs_documents case must not silently flip to
        # complete on a GET — it completes on its next run (re-run-on-complete / new upload).
        rung2 = (
            _rung2_three_numbers(case, plan_coverage=plan_cov)
            if (case is not None and case.status in ("audit_running", "audit_complete"))
            else None
        )
        if rung2 is not None:
            log.info(
                "orchestrator.rung2_completion",
                case_file_id=case_file_id,
                anchor_kind=rung2["anchor_kind"],
                missing_inputs=rung2["missing_inputs"],
            )
            return AuditResult(
                case_file_id=case_file_id,
                status="complete",
                audit=ThreeNumberAudit(
                    provider_billed=rung2["provider_billed"],
                    eob_member_responsibility=rung2["eob_member_responsibility"],
                    tyndale_computed=rung2["tyndale_computed"],
                    tyndale_computed_low=rung2["tyndale_computed_low"],
                    tyndale_computed_high=rung2["tyndale_computed_high"],
                    computed_source="engine_rung2",
                ),
                findings=findings,
                summary=composed,
                audit_provenance=provenance,
                disclosure=disclosure,
            )
        log.warning("orchestrator.no_three_number_finding", case_file_id=case_file_id)
        # Read back the persisted honest reason (set at finalize). Default to needs_documents:
        # a re-fetch of a document-poor case is user-actionable, not a system failure.
        reason = (case.audit_incomplete_reason if case else None) or "needs_documents"
        return AuditResult(
            case_file_id=case_file_id,
            status="audit_incomplete",
            audit=None,
            findings=findings,
            summary=composed,
            audit_provenance=provenance,
            disclosure=disclosure,
            incomplete_reason=reason,
            documents_needed=(
                _documents_needed(case, plan_sbc=plan_sbc)
                if reason == "needs_documents"
                else []
            ),
        )

    # Tier ≥ 2 renders a RANGE, never a point (doc 38 §2.5; e2e 2026-09-23 M5). The Math
    # Person's figure was computed with priors standing in for the inputs the documents
    # never stated ("based on a typical deductible") — a benchmark substitution — but the
    # agent writes one number. The rung-2 sweep over the same document money and the same
    # priors brackets it; the agent's point is kept as the figure and widened into the
    # bracket if it falls outside. No document anchor → no honest range → the point stands
    # and the provenance says why.
    three_numbers = _bracket_agent_point(three_numbers, case, plan_cov, disclosure, provenance)
    return AuditResult(
        case_file_id=case_file_id,
        status="complete",
        audit=ThreeNumberAudit(**three_numbers),
        findings=findings,
        summary=composed,
        audit_provenance=provenance,
        disclosure=disclosure,
    )


def _bracket_agent_point(three_numbers: dict, case, plan_cov, disclosure, provenance) -> dict:
    if disclosure is None or disclosure.tier < 2 or three_numbers.get("tyndale_computed") is None:
        return three_numbers
    if three_numbers.get("tyndale_computed_low") is not None:
        return three_numbers  # already a range
    rung2 = _rung2_three_numbers(case, plan_coverage=plan_cov) if case is not None else None
    point = float(three_numbers["tyndale_computed"])
    if rung2 is None or rung2.get("tyndale_computed_low") is None or rung2.get("tyndale_computed_high") is None:
        reason = "no document-stated money to anchor a range" if rung2 is None else "the priors it needs are still placeholders"
        provenance.assumptions.append(
            f"the computed figure rests on typical values for inputs your documents don't state, "
            f"shown as a point because {reason}"
        )
        return three_numbers
    low = round(min(float(rung2["tyndale_computed_low"]), point), 2)
    high = round(max(float(rung2["tyndale_computed_high"]), point), 2)
    if low == high:
        return three_numbers  # the sweep collapsed onto the point — nothing to bracket
    return {**three_numbers, "tyndale_computed_low": low, "tyndale_computed_high": high}


# ===========================================================================
# Phase 2I — two-phase audit: extract -> confirmations -> finalize
# ===========================================================================

# Fixture line items for the no-real-Claude path (tests + dev). An ER+imaging
# bill: a high-complexity ER visit E/M code (high_risk — upcoding-prone) and the
# MRI. Plain-language translations describe WHAT HAPPENED, never necessity.
_FIXTURE_LINE_ITEMS = [
    {
        "code": "99284",
        "code_system": "CPT",
        "raw_description": "EMERGENCY DEPT VISIT, MODERATE-HIGH COMPLEXITY",
        "plain_language_translation": "A higher-complexity emergency room visit.",
        "plain_language_context": "ER visits coded at this level usually involve a longer stay or a more complicated situation.",
        "high_risk": True,
        "billed_amount": 1200.0,
        "units": 1,
    },
    {
        "code": "70553",
        "code_system": "CPT",
        "raw_description": "MRI BRAIN W/O & W/ CONTRAST",
        "plain_language_translation": "An MRI scan of your brain, done both with and without contrast dye.",
        "plain_language_context": "",
        "high_risk": False,
        "billed_amount": 1200.0,
        "units": 1,
    },
]


def _fixture_line_items() -> list[dict]:
    return [{"line_item_id": str(uuid4()), **it} for it in _FIXTURE_LINE_ITEMS]


# Honest, actionable copy shown on the encounter screen when real extraction produced nothing —
# instead of fabricated line items (Grounding & Graceful Degradation Doctrine).
EXTRACTION_FAILED_MESSAGE = (
    "We couldn't read your documents well enough to check them. Try uploading a clearer "
    "photo or a PDF — good lighting, all four corners in frame, one document per image."
)

# needs_documents at EXTRACT time (2026-08-18, Phil's ruling): the document READ fine and
# carries a real amount — it just has no line-item detail to audit (a collections notice, a
# summary statement). The ask is for MORE PAPER, not a better photo.
NEEDS_DOCUMENTS_EXTRACT_MESSAGE = (
    "We can read this document and the amount on it — but it doesn't include the line-item "
    "detail we audit. Add the itemized bill or the EOB for this visit and we'll take it "
    "from there."
)

# A dollar-looking figure — the "readable amount" test for the needs_documents split.
_AMOUNT_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{2})?|\b\d{1,3}(?:,\d{3})*\.\d{2}\b")


def _any_recognized_doc_has_amount(cf) -> bool:
    """True when some extracted, classified document's stored text shows a dollar figure —
    the evidence that the upload is auditable in principle and the honest ask is for the
    itemized detail, not a re-photograph."""
    for d in (cf.documents if cf else None) or []:
        if not isinstance(d, dict):
            continue
        if (d.get("extraction_status") or "extracted") != "extracted":
            continue
        if (d.get("document_type") or "unclassified") == "unclassified":
            continue
        if _AMOUNT_RE.search(str(d.get("ocr_text") or d.get("ocr_text_preview") or "")):
            return True
    return False

# Distinct from extraction_failed: the document(s) READ fine, they just aren't a medical bill or
# insurance document — so there's nothing to audit. Name the file(s) so the user knows exactly
# which upload was the problem, and point them at what Tyndale can actually help with.
_FRIENDLY_DOC_TYPE = {
    "insurance_card": "an insurance card", "sbc": "a plan summary",
    "gfe": "a good-faith estimate", "clinical_record": "a medical record",
    "clinical_note": "a clinical note", "medical_record": "a medical record",
    "unclassified": "something I couldn't place",
}


def _detected_doc_type(documents) -> str | None:
    """Plain-language name for {detected_doc_type} (§5.3). None when nothing was classified —
    which degrades rather than guessing at what the upload was."""
    for d in documents or []:
        t = d.get("document_type") if isinstance(d, dict) else getattr(d, "document_type", None)
        if t and t != "unclassified":
            return _FRIENDLY_DOC_TYPE.get(t, t.replace("_", " "))
    for d in documents or []:
        t = d.get("document_type") if isinstance(d, dict) else getattr(d, "document_type", None)
        if t:
            return _FRIENDLY_DOC_TYPE.get(t)
    return None


def _with_source_line(f: FindingOut) -> FindingOut:
    """E4/H3 — stamp the grounding line onto every finding the API returns, so a client cannot
    render a claim without either its source or the explicit no-source state. Also the X5
    error_type annotation seam (same one-chokepoint reasoning; see sources/error_types)."""
    f.source_line, f.has_source = finding_source_line(f)
    # B5: the [A]/[B] split + chip enforcement, at the same one chokepoint.
    from app.agents.grounding import apply_finding_tier
    from app.sources.error_types import annotate_error_type
    from app.sources.gameplan import humanize_category

    f.title = humanize_category(f.category or "")
    return annotate_error_type(apply_finding_tier(f))


def not_a_bill_message(filenames: list[str], documents=None) -> str:
    """The wrong-document redirect message (§A2 state 2). When the classifier placed the
    upload (insurance card / SBC / GFE / clinical record), the TYPED branch copy renders —
    each with its own honest next step. Falls back to the generic line for a genuinely
    unplaceable upload, or when the branch key isn't authored yet."""
    named = ", ".join(f"“{n}”" for n in filenames) if filenames else "what you uploaded"
    branch = classify_wrong_document(documents) if documents else None
    if branch is not None:
        # Brock's §5.3 names the DETECTED DOCUMENT TYPE ({detected_doc_type}), not the filename.
        # (The prior engineering copy named the file; his authored version is the authority —
        # flagged in the pull-in summary so he can restore file-naming if he wants it.)
        text = orchestration_step(branch.key, detected_doc_type=_detected_doc_type(documents))
        if not text.startswith("<MISSING-script:"):
            return text
    return (
        f"This doesn't look like a medical bill or insurance document: {named}. "
        "Upload a bill, an Explanation of Benefits (EOB), an insurance card, or a plan "
        "summary and I'll check it for you."
    )


def _grounded_line_items(
    cf: CaseFile | None, line_items: list[dict]
) -> tuple[list[dict], list[str]]:
    """(kept, dropped_codes) — keep only line items whose base code appears in some uploaded
    document's OCR text.

    Conservative by design:
      * no full text stored on ANY extracted doc (pre-guard uploads) → keep everything;
        a 1000-char preview can't prove absence on a long bill.
      * items with no code, or codes shorter than 4 chars, are kept — the guard convicts
        on strong evidence only (the prompt-bleed class is 5-char CPT/HCPCS examples).
      * modifier forms match on the base ("73721-26" is grounded by "73721").
    A falsely-dropped real item (e.g. the code itself mis-OCR'd) degrades to the honest
    ask-for-a-clearer-photo path — recoverable, unlike a fabricated charge shown as real.
    """
    haystack = _document_haystack(cf)
    if haystack is None:
        return line_items, []
    kept: list[dict] = []
    dropped: list[str] = []
    for item in line_items:
        code = str(item.get("code") or "").strip().upper()
        base = code.split("-", 1)[0].strip()
        if len(base) < 4 or base in haystack:
            kept.append(item)
        else:
            dropped.append(code)
    return kept, dropped


def _documents_projection(cf: CaseFile | None) -> list[DocumentExtraction]:
    """Per-document extraction provenance (which uploads were read vs failed) for the
    encounter + admin UI, so a degraded audit can never be mistaken for a real one."""
    out: list[DocumentExtraction] = []
    for d in (cf.documents if cf else None) or []:
        if not isinstance(d, dict):
            continue
        out.append(
            DocumentExtraction(
                filename=d.get("filename") or "document",
                document_type=d.get("document_type"),
                extraction_status=d.get("extraction_status") or "unknown",
                ocr_text_chars=int(d.get("ocr_text_chars") or 0),
            )
        )
    return out


async def _load_case(case_file_id: str) -> CaseFile | None:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()


async def _documents_needed_with_plan(case_file_id: str) -> list[DocumentNeed]:
    """Checklist for one case with the user's plan-level SBC counted (settings item 5)."""
    from app.sources.plan_docs import plan_sbc_state

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        plan_sbc = False
        if case is not None:
            plan_sbc, _ = await plan_sbc_state(s, case.user_id)
    return _documents_needed(case, plan_sbc=plan_sbc)


async def extract_line_items(case_file_id: str) -> ExtractResult:
    """Phase 1 of the audit — Bill Detective translates each line item to plain
    language. Persists them to case_files.line_items; sets status
    encounter_verification_pending."""
    settings = get_settings()
    use_real = settings.use_real_claude and (
        _has_real_anthropic_creds(settings) or settings.litellm_proxy_url
    )

    bd_tool_calls: int | None = None
    if use_real:
        # e2e 2026-09-23 B4: reading + classifying the documents is a MACHINE phase like the
        # audit. `open` already reads as working, but a case's status can be anything a prior
        # run left ("extraction_failed" on a re-upload, an old "encounter_verification_pending"
        # while a new document is read): a CAS to `in_progress` makes every reconcile during
        # extraction render only the status card, whatever the case was doing before.
        for prior in ("open", "extraction_failed", "not_a_bill", "encounter_verification_pending"):
            if await _set_status(case_file_id, "in_progress", expected_status=prior):
                break
        log.info("orchestrator.extract.real", case_file_id=case_file_id)
        bd = await bill_detective.run(case_file_id, mode="translate")
        bd_tool_calls = len(bd.tool_calls)
        log.info(
            "orchestrator.extract.bd_done",
            case_file_id=case_file_id,
            tool_calls=bd_tool_calls,
            usage=bd.usage,
        )

    # Read whatever the agent persisted.
    cf = await _load_case(case_file_id)
    line_items = list(cf.line_items) if (cf and cf.line_items) else []

    # GROUNDING GUARD (dev sweep 2026-08-17): under thin OCR (a photographed bill), the
    # translate agent can echo a worked example from its own skill/tool prompts into the
    # persisted line items — a fabricated charge on the user's encounter screen, the exact
    # failure the Grounding Doctrine names as the worst one. Deterministic check: a coded
    # item whose base code appears in NO uploaded document's OCR text did not come from the
    # user's documents, so it does not survive. Applies only in real mode (fixture items are
    # by definition not in any document) and only when full text is stored (legacy cases
    # carry a 1000-char preview only — insufficient evidence to convict, so nothing drops).
    if use_real and line_items:
        line_items, dropped = _grounded_line_items(cf, line_items)
        if dropped:
            log.error(
                "orchestrator.translate.ungrounded_line_items_dropped",
                case_file_id=case_file_id,
                dropped_codes=dropped,
                kept=len(line_items),
            )
            # Persist the filtered list NOW — fabricated rows must not survive in the DB
            # even if a later step fails (the honest no-item paths below return without
            # rewriting line_items). The drop is also a case-scoped TRIPWIRE record
            # (research_log) — the human-review canary trigger reads it.
            async with AsyncSessionLocal() as s:
                row = (
                    await s.execute(
                        select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id))
                    )
                ).scalar_one_or_none()
                if row is not None:
                    row.line_items = line_items
                    await _append_tripwire(
                        case_file_id, "translate_drop", codes=list(dropped), session=s
                    )
                    await s.commit()

    if not line_items:
        # Real translate produced nothing. Decide the honest terminal state from DOCUMENT-READABILITY
        # TRUTH (per-document OCR provenance) — a case must NEVER land on a 0-item encounter screen
        # (the reproduced bug: corrupt / blank / non-bill uploads dead-ended there under "0 of 0").
        # NEVER serve fixtures as the user's bill in real mode: two honest degradations stacking into
        # a confident fabrication is the worst failure this product can have. Fixture mode (use_real
        # False — dev/CI/demo without Claude) is the ONLY path that may serve fixtures, and it does
        # so regardless of OCR status so local dev works with placeholder DI creds.
        if use_real:
            docs = _documents_projection(cf)
            readable = [
                d for d in docs if d.extraction_status == "extracted" and d.ocr_text_chars > 0
            ]
            # A doc is "recognized" if the classifier assigned it ANY medical/insurance type (it
            # only ever returns 'unclassified' for a document it can't place). not_a_bill is
            # reserved for genuinely non-medical uploads — a recognized-but-non-bill doc (collections
            # notice, denial letter, insurance card, plan summary) is still a medical document and
            # must NOT be mislabeled "not a medical bill".
            readable_recognized = [
                d for d in readable if (d.document_type or "unclassified") != "unclassified"
            ]

            def _degrade(status: str, message: str, event: str) -> ExtractResult:
                log.error(
                    event,
                    case_file_id=case_file_id,
                    bd_tool_calls=bd_tool_calls,
                    documents=[
                        {
                            "filename": d.filename,
                            "document_type": d.document_type,
                            "extraction_status": d.extraction_status,
                            "ocr_text_chars": d.ocr_text_chars,
                        }
                        for d in docs
                    ],
                )
                return ExtractResult(
                    case_file_id=case_file_id,
                    status=status,
                    line_items=[],
                    intro_message=DEFAULT_INTRO_MESSAGE,
                    extraction_message=message,
                    documents=docs,
                )

            # (a) Every uploaded document failed to read (DI error or empty OCR) → extraction_failed.
            if docs and not readable:
                await _set_status(case_file_id, "extraction_failed")
                return _degrade(
                    "extraction_failed", EXTRACTION_FAILED_MESSAGE,
                    "orchestrator.extract.all_documents_unreadable",
                )

            # (b) At least one document read fine, but NONE is recognizable as a medical/insurance
            # document at all (e.g. a photo of something unrelated) → nothing to audit. A distinct
            # honest state, naming the file(s), so the user isn't stranded on a 0-item encounter.
            if readable and not readable_recognized:
                await _set_status(case_file_id, "not_a_bill")
                return _degrade(
                    "not_a_bill",
                    not_a_bill_message([d.filename for d in readable], readable),
                    "orchestrator.extract.readable_but_not_a_bill",
                )

            # (b2) WRONG-DOCUMENT REDIRECT (§A2 state 2): every readable document is a real
            # medical/insurance document that simply carries no auditable charges — an
            # insurance card, a plan summary/SBC, a GFE, a clinical record. "We couldn't read
            # line items" is the wrong framing for those; each gets its typed redirect + next
            # step instead. (A doc that COULD yield line items falls through to (c) below.)
            wrong = classify_wrong_document(readable_recognized)
            if wrong is not None:
                await _set_status(case_file_id, "not_a_bill")
                return _degrade(
                    "not_a_bill",
                    not_a_bill_message([d.filename for d in readable], readable_recognized),
                    "orchestrator.extract.wrong_document_redirect",
                )

            # (c) We recognized a medical document but extracted no billable line items.
            # Split (2026-08-18, Phil's ruling — needs_documents governs): a recognized doc
            # with a READABLE AMOUNT (a collections notice, a summary statement) is
            # auditable in principle — the user needs to SUPPLY the itemized detail, not
            # re-photograph anything. That's the needs_documents chase (the real Beloit
            # day-one behavior). extraction_failed stays reserved for documents we
            # genuinely could not read. Never falls through to fixtures either way.
            if _any_recognized_doc_has_amount(cf):
                await _set_status(
                    case_file_id, "audit_incomplete", incomplete_reason="needs_documents"
                )
                return _degrade(
                    "needs_documents", NEEDS_DOCUMENTS_EXTRACT_MESSAGE,
                    "orchestrator.extract.recognized_amount_needs_documents",
                )
            await _set_status(case_file_id, "extraction_failed")
            return _degrade(
                "extraction_failed", EXTRACTION_FAILED_MESSAGE,
                "orchestrator.extract.degraded_no_line_items",
            )

        # Explicit fixture mode ONLY (use_real is False — dev/CI/demo without Claude).
        line_items = _fixture_line_items()

    # Phase 2L: every line item must carry example scenarios for the encounter
    # UI (the translate pass may omit them; fixtures + pre-2L rows predate them).
    backfill_scenarios(line_items)

    # Persist the (possibly backfilled) line items so the idempotent
    # GET .../line-items re-fetch and the diagnose pass both see the scenarios.
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        if row is not None:
            row.line_items = line_items
            await s.commit()

    # INVARIANT (item 4): a case may NEVER enter encounter_verification_pending with zero line
    # items. Every empty-extraction path above returns an honest terminal state, so line_items is
    # non-empty here — but guard anyway. A future regression (or a fixture that yields nothing)
    # must degrade honestly, never strand the user on a "0 of 0 confirmed" encounter screen.
    if not line_items:
        log.error("orchestrator.extract.zero_item_invariant_tripped", case_file_id=case_file_id)
        await _set_status(case_file_id, "extraction_failed")
        return ExtractResult(
            case_file_id=case_file_id,
            status="extraction_failed",
            line_items=[],
            intro_message=DEFAULT_INTRO_MESSAGE,
            extraction_message=EXTRACTION_FAILED_MESSAGE,
            documents=_documents_projection(cf),
        )

    await _set_status(case_file_id, "encounter_verification_pending")
    return ExtractResult(
        case_file_id=case_file_id,
        status="encounter_verification_pending",
        line_items=[LineItem(**it) for it in line_items],
        intro_message=DEFAULT_INTRO_MESSAGE,
        documents=_documents_projection(cf),
    )


async def submit_confirmations(
    case_file_id: str,
    confirmations: list[LineItemConfirmation],
) -> ConfirmationsAccepted:
    """Persist confirmations + write feedback_events (value_confirmation,
    confirmation_kind=encounter_lineitem). Each mismatch (a 'no', or a
    'not_sure' on a high-risk item) becomes an encounter_mismatch finding stub
    that Bill Detective pursues during finalize. Sets status encounter_verified."""
    cf = await _load_case(case_file_id)
    if cf is None:
        raise ValueError(f"case_file {case_file_id} not found")
    line_item_by_id = {it["line_item_id"]: it for it in (cf.line_items or [])}
    user_id = cf.user_id

    mismatches = 0
    async with AsyncSessionLocal() as s:
        # Persist the raw confirmations on the case file.
        row = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one()
        row.encounter_confirmations = [c.model_dump() for c in confirmations]

        for c in confirmations:
            li = line_item_by_id.get(c.line_item_id, {})
            translation = li.get("plain_language_translation", "")
            high_risk = bool(li.get("high_risk", False))

            # Feedback event — high-value label for the L06 de-id pipeline.
            # improvement_consent defaults False until Phase 2J wires the toggle.
            event_payload = {
                "event_id": str(uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "case_file_id": case_file_id,
                "feedback_type": "value_confirmation",
                "value_confirmation": {
                    "confirmation_kind": "encounter_lineitem",
                    "field": "line_item_response",
                    "tyndale_extracted": translation,
                    "user_corrected": c.response + ((" — " + c.user_note) if c.user_note else ""),
                    "was_correct": c.response == "yes",
                },
                "improvement_consent": False,
                "promoted_to_eval": False,
            }
            fe = FeedbackEvent(
                case_file_id=UUID(case_file_id),
                user_id=user_id,
                response_id=c.line_item_id,
                feedback_type="value_confirmation",
                improvement_consent=False,
                payload=event_payload,
            )
            s.add(fe)

            # Mismatch -> encounter_mismatch candidate finding.
            is_mismatch = c.response == "no" or (c.response == "not_sure" and high_risk)
            if is_mismatch:
                mismatches += 1
                category = "upcoding_candidate" if high_risk else "phantom_charge_candidate"
                s.add(
                    Finding(
                        finding_id=uuid4(),
                        case_file_id=UUID(case_file_id),
                        finding_type="encounter_mismatch",
                        category=category,
                        subagent_source="encounter_verification",
                        voice_tier="A",
                        facts={
                            "line_item_id": c.line_item_id,
                            "code": li.get("code"),
                            "raw_description": li.get("raw_description"),
                            "plain_language_translation": translation,
                            "user_response": c.response,
                            "user_note": c.user_note,
                            "high_risk": high_risk,
                        },
                        legal_claim=None,
                        recommendation={
                            "action": "Bill Detective will pursue this against the upcoding / phantom-charge rules during the audit.",
                            "reasoning": "User indicated this line item does not match what actually happened.",
                        },
                    )
                )
        await s.commit()

    await _set_status(case_file_id, "encounter_verified")
    log.info(
        "orchestrator.confirmations.recorded",
        case_file_id=case_file_id,
        count=len(confirmations),
        mismatches=mismatches,
    )
    return ConfirmationsAccepted(
        case_file_id=case_file_id,
        status="audit_running",
        confirmations_recorded=len(confirmations),
        mismatches=mismatches,
    )


async def _persist_mri_fixture_finding(case_file_id: str) -> None:
    """Fixture-path finalize: ensure a payer-side three-number finding row
    exists so _assemble_result can surface the audit. Idempotent — skips if a
    cost_sharing_miscalculation finding already exists for the case. (Filters on
    category, not just finding_type: an accumulator_discrepancy finding from the
    CO-12B cross-check is also payer_side but carries no three-number facts, so
    it must not suppress this row.)"""
    async with AsyncSessionLocal() as s:
        existing = (
            await s.execute(
                select(Finding)
                .where(Finding.case_file_id == UUID(case_file_id))
                .where(Finding.finding_type == "payer_side")
                .where(Finding.category == "cost_sharing_miscalculation")
            )
        ).first()
        if existing is not None:
            return
        s.add(
            Finding(
                finding_id=uuid4(),
                case_file_id=UUID(case_file_id),
                finding_type="payer_side",
                category="cost_sharing_miscalculation",
                subagent_source="math_person",
                voice_tier="B",
                facts={
                    "provider_billed": 1200.0,
                    "eob_member_responsibility": 1200.0,
                    "tyndale_computed": 560.0,
                    "gap": 640.0,
                },
                legal_claim={
                    "claim": "The payer appears to have miscalculated member cost-sharing.",
                    "marker": "[PLACEHOLDER_AUTHORITY §000, src_0a1b2c3d]",
                    "citations": [
                        {
                            "authority": "PLACEHOLDER_AUTHORITY",
                            "section": "§000",
                            "src_id": "src_0a1b2c3d",
                            "marker": "[PLACEHOLDER_AUTHORITY §000, src_0a1b2c3d]",
                        }
                    ],
                },
                recommendation={
                    "action": "Call the payer to dispute the cost-sharing math; request a corrected EOB.",
                    "reasoning": "Tyndale's independent figure ($560) is $640 below the EOB's claimed $1,200.",
                },
            )
        )
        await s.commit()


async def finalize_audit(case_file_id: str) -> AuditResult:
    """Phase 2 of the audit — Bill Detective re-diagnoses with confirmations as
    input, Math Person runs the three-number audit, Lead Planner composes. Sets
    status audit_running -> audit_complete."""
    settings = get_settings()
    await _set_status(case_file_id, "audit_running")

    use_real = settings.use_real_claude and (
        _has_real_anthropic_creds(settings) or settings.litellm_proxy_url
    )

    cf = await _load_case(case_file_id)
    confirmations = list(cf.encounter_confirmations) if cf else []

    # CO-12B: the deterministic accumulator cross-check runs on BOTH the real and
    # fixture finalize paths — it is pure DB math (no LLM), so dev/fixture runs get
    # the same discrepancy finding a production run would. The no-EOB guard inside
    # keeps it a no-op for cases without EOB data (all existing fixture tests).
    accumulator = await _run_accumulator_cross_check(case_file_id)
    await _heartbeat(case_file_id)  # phase boundary: cross-check done, agents next

    # Item 1: run under the wall-clock + regen budget, always resolve to a TERMINAL status
    # (never leave the case stuck in audit_running), and record the run's timing/regens.
    budget, started = _new_audit_budget(settings)
    token = set_audit_budget(budget)
    path = claude_path_label(settings)
    try:
        if use_real:
            log.info("orchestrator.finalize.real", case_file_id=case_file_id)
            # Agents run concurrently on their own sessions (see _run_real_agents).
            composed, budget_stopped, stage_ms = await _run_real_agents(
                case_file_id, accumulator, confirmations, budget
            )
        else:
            log.info("orchestrator.finalize.fixture", case_file_id=case_file_id)
            await _persist_mri_fixture_finding(case_file_id)
            composed, budget_stopped, stage_ms = mri_audit_fixture(case_file_id).summary, False, {}
        return await _finalize_result(
            case_file_id, composed, budget, budget_stopped, started, stage_ms, path,
            manage_status=True,
        )
    except Exception as exc:  # noqa: BLE001 — never leave the case in audit_running forever
        # A crash is not user-actionable — it is a system_error (apology copy + a real alert).
        await _set_status(case_file_id, "audit_incomplete", incomplete_reason="system_error")
        record_system_alert()
        record_audit_run(
            duration_seconds=round(time.monotonic() - started, 2), reason="error",
            regens=budget.regens_used, path=path, stage_ms={},
        )
        log.error(
            "orchestrator.finalize.failed",
            case_file_id=case_file_id, error_class=type(exc).__name__, exc_info=True,
        )
        raise
    finally:
        reset_audit_budget(token)
