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

import time
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from app.agents import bill_detective, lead_planner, math_person
from app.agents.audit_budget import AuditBudget, reset_audit_budget, set_audit_budget
from app.agents.llm_health import claude_path_label, record_audit_run
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
    FindingOut,
    ThreeNumberAudit,
)
from app.schemas.encounter import (
    DEFAULT_INTRO_MESSAGE,
    ConfirmationsAccepted,
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


async def _set_status(case_file_id: str, status: str) -> None:
    async with AsyncSessionLocal() as s:
        cf = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        if cf is not None:
            cf.status = status
            await s.commit()


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


async def _run_real_agents(
    case_file_id: str,
    accumulator: dict | None,
    confirmations: list[dict],
    budget: AuditBudget,
    session,
) -> tuple[str, bool, dict]:
    """Bill Detective → Math Person → Lead Planner under the audit budget (Item 1). Between
    agents, if the budget is spent, STOP at the safe boundary — don't start another
    multi-minute turn. Math Person writes the three-number finding, so it survives a Lead
    Planner cutoff. Returns (composed_summary, budget_stopped, stage_ms)."""
    stage_ms: dict[str, int] = {}
    budget_stopped = False

    t = time.monotonic()
    bd = await bill_detective.run(
        case_file_id, mode="diagnose", confirmations=confirmations, session=session
    )
    stage_ms["bill_detective_ms"] = _ms(t)
    budget_stopped = budget_stopped or bd.budget_stopped
    log.info(
        "orchestrator.bill_detective.done",
        case_file_id=case_file_id, tool_calls=len(bd.tool_calls), usage=bd.usage,
    )

    mp_text = ""
    if budget.expired():
        log.warning("orchestrator.budget.skipped_agent", case_file_id=case_file_id, stage="math_person")
        budget_stopped = True
    else:
        t = time.monotonic()
        mp = await math_person.run(case_file_id, accumulator=accumulator, session=session)
        stage_ms["math_person_ms"] = _ms(t)
        mp_text = mp.final_text
        budget_stopped = budget_stopped or mp.budget_stopped
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
        lp = await lead_planner.compose_final(case_file_id, bd.final_text, mp_text, session=session)
        stage_ms["lead_planner_ms"] = _ms(t)
        composed = lp.final_text
        budget_stopped = budget_stopped or lp.budget_stopped
        log.info(
            "orchestrator.lead_planner.done",
            case_file_id=case_file_id, tool_calls=len(lp.tool_calls), usage=lp.usage,
            stop_action=lp.stop_action, human_review_needed=lp.human_review_needed,
        )

    return composed, budget_stopped, stage_ms


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
    if budget.expired() or budget_stopped:
        terminal, reason = "audit_incomplete", "budget_exceeded"
    elif result.audit is not None:
        terminal, reason = "audit_complete", None
    else:
        terminal, reason = "audit_incomplete", "no_three_number_finding"
    if reason:
        # Keep any computed three numbers on the result — it's a PARTIAL, not a blank.
        result = result.model_copy(update={"status": terminal, "incomplete_reason": reason})
    if manage_status:
        await _set_status(case_file_id, terminal)
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
    return result


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
        async with AsyncSessionLocal() as audit_session:
            composed, budget_stopped, stage_ms = await _run_real_agents(
                case_file_id, accumulator, [], budget, audit_session
            )
            await audit_session.commit()
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


def _regime_provenance(case: CaseFile | None) -> AuditProvenance:
    """The coverage-regime context this audit ran under (Sprint B, DL-82). Every
    non-commercial or unconfirmed regime still uses the generic path but carries an
    explicit assumption naming the pending population corpus, so nothing silently
    pretends to have applied population-specific rules."""
    regime = case.coverage_regime if case else None
    detection = (case.regime_detection if case else None) or {}
    verified = bool(detection.get("verified"))
    assumptions: list[str] = []
    if not regime:
        assumptions.append(
            "coverage regime not yet confirmed — audited under generic commercial rules (DL-82)"
        )
    elif regime != "commercial":
        assumptions.append(
            f"audited under generic commercial rules — {regime} rules corpus pending (DL-82)"
        )
    if not get_settings().enable_nsa_checks:
        assumptions.append(
            "surprise-billing / No Surprises Act checks are not yet enabled "
            "(pending the 50-state seed — DL-81/DL-88)"
        )
    return AuditProvenance(
        coverage_regime=regime, regime_verified=verified, assumptions=assumptions
    )


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
    provenance = _regime_provenance(case)
    # A persisted accumulator_discrepancy is the cross-validation material signal (DL-72).
    cv_material = any(getattr(f, "category", None) == "accumulator_discrepancy" for f in rows)
    disclosure = _compute_disclosure(
        case.coverage if case else None, cross_validation_material=cv_material
    )

    findings: list[FindingOut] = []
    three_numbers: dict | None = None
    for f in rows:
        facts = f.facts or {}
        # Citations live inside legal_claim["citations"] (Finding has no
        # separate citations column — see app/tools/db_tools.py).
        raw_citations = []
        if isinstance(f.legal_claim, dict):
            raw_citations = f.legal_claim.get("citations") or []
        citations = [Citation(**c) for c in raw_citations if isinstance(c, dict)]
        findings.append(
            FindingOut(
                finding_id=str(f.finding_id),
                finding_type=f.finding_type,
                category=f.category,
                subagent_source=f.subagent_source or "unknown",
                voice_tier=f.voice_tier or "B",
                facts=facts,
                legal_claim=f.legal_claim,
                recommendation=f.recommendation,
                citations=citations,
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
                        "provider_billed": float(pb),
                        "eob_member_responsibility": float(eob),
                        "tyndale_computed": float(tc),
                    }
                except (TypeError, ValueError):
                    log.warning(
                        "orchestrator.three_number_coercion_failed",
                        case_file_id=case_file_id,
                        finding_id=str(f.finding_id),
                        facts_subset={"pb": pb, "eob": eob, "tc": tc},
                    )

    if three_numbers is None:
        # Real agents ran but wrote no three-number finding. NEVER return {0,0,0}
        # with status="complete" — that presents "you owe $0" as a finished audit
        # (CO-15 T2.3). Surface a degraded status with no audit block; the findings
        # + composed summary still ship so the user isn't dead-ended (Graceful
        # Degradation Doctrine).
        log.warning("orchestrator.no_three_number_finding", case_file_id=case_file_id)
        return AuditResult(
            case_file_id=case_file_id,
            status="audit_incomplete",
            audit=None,
            findings=findings,
            summary=composed,
            audit_provenance=provenance,
            disclosure=disclosure,
        )

    return AuditResult(
        case_file_id=case_file_id,
        status="complete",
        audit=ThreeNumberAudit(**three_numbers),
        findings=findings,
        summary=composed,
        audit_provenance=provenance,
        disclosure=disclosure,
    )


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


async def _load_case(case_file_id: str) -> CaseFile | None:
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()


async def extract_line_items(case_file_id: str) -> ExtractResult:
    """Phase 1 of the audit — Bill Detective translates each line item to plain
    language. Persists them to case_files.line_items; sets status
    encounter_verification_pending."""
    settings = get_settings()
    use_real = settings.use_real_claude and (
        _has_real_anthropic_creds(settings) or settings.litellm_proxy_url
    )

    if use_real:
        log.info("orchestrator.extract.real", case_file_id=case_file_id)
        bd = await bill_detective.run(case_file_id, mode="translate")
        log.info(
            "orchestrator.extract.bd_done",
            case_file_id=case_file_id,
            tool_calls=len(bd.tool_calls),
            usage=bd.usage,
        )

    # Read whatever the agent persisted; fall back to fixture line items if the
    # translate pass produced none (or we're on the no-Claude path).
    cf = await _load_case(case_file_id)
    line_items = list(cf.line_items) if (cf and cf.line_items) else []
    if not line_items:
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

    await _set_status(case_file_id, "encounter_verification_pending")
    return ExtractResult(
        case_file_id=case_file_id,
        status="encounter_verification_pending",
        line_items=[LineItem(**it) for it in line_items],
        intro_message=DEFAULT_INTRO_MESSAGE,
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

    # Item 1: run under the wall-clock + regen budget, always resolve to a TERMINAL status
    # (never leave the case stuck in audit_running), and record the run's timing/regens.
    budget, started = _new_audit_budget(settings)
    token = set_audit_budget(budget)
    path = claude_path_label(settings)
    try:
        if use_real:
            log.info("orchestrator.finalize.real", case_file_id=case_file_id)
            async with AsyncSessionLocal() as audit_session:
                composed, budget_stopped, stage_ms = await _run_real_agents(
                    case_file_id, accumulator, confirmations, budget, audit_session
                )
                await audit_session.commit()
        else:
            log.info("orchestrator.finalize.fixture", case_file_id=case_file_id)
            await _persist_mri_fixture_finding(case_file_id)
            composed, budget_stopped, stage_ms = mri_audit_fixture(case_file_id).summary, False, {}
        return await _finalize_result(
            case_file_id, composed, budget, budget_stopped, started, stage_ms, path,
            manage_status=True,
        )
    except Exception as exc:  # noqa: BLE001 — never leave the case in audit_running forever
        await _set_status(case_file_id, "audit_incomplete")
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
