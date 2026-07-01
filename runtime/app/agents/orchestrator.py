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

from datetime import datetime, timezone
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from app.agents import bill_detective, lead_planner, math_person
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.schemas.case_file import AuditResult, Citation, FindingOut, ThreeNumberAudit
from app.schemas.encounter import (
    DEFAULT_INTRO_MESSAGE,
    ConfirmationsAccepted,
    ExtractResult,
    LineItem,
    LineItemConfirmation,
)
from app.agents.example_scenarios import backfill_scenarios
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

    async with AsyncSessionLocal() as audit_session:
        bd = await bill_detective.run(case_file_id, session=audit_session)
        log.info(
            "orchestrator.bill_detective.done",
            case_file_id=case_file_id,
            tool_calls=len(bd.tool_calls),
            usage=bd.usage,
        )

        mp = await math_person.run(case_file_id, session=audit_session)
        log.info(
            "orchestrator.math_person.done",
            case_file_id=case_file_id,
            tool_calls=len(mp.tool_calls),
            usage=mp.usage,
        )

        lp = await lead_planner.compose_final(
            case_file_id, bd.final_text, mp.final_text, session=audit_session
        )
        log.info(
            "orchestrator.lead_planner.done",
            case_file_id=case_file_id,
            tool_calls=len(lp.tool_calls),
            usage=lp.usage,
            stop_action=lp.stop_action,
            human_review_needed=lp.human_review_needed,
        )
        await audit_session.commit()

    # Assemble the API response from persisted findings.
    return await _assemble_result(case_file_id, lp.final_text)


async def _assemble_result(case_file_id: str, composed: str) -> AuditResult:
    """Read findings from Postgres and project to AuditResult shape."""
    async with AsyncSessionLocal() as s:
        rows = (
            (await s.execute(select(Finding).where(Finding.case_file_id == UUID(case_file_id))))
            .scalars()
            .all()
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
        )

    return AuditResult(
        case_file_id=case_file_id,
        status="complete",
        audit=ThreeNumberAudit(**three_numbers),
        findings=findings,
        summary=composed,
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
    payer_side finding already exists for the case."""
    async with AsyncSessionLocal() as s:
        existing = (
            await s.execute(
                select(Finding)
                .where(Finding.case_file_id == UUID(case_file_id))
                .where(Finding.finding_type == "payer_side")
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

    composed = ""
    if use_real:
        log.info("orchestrator.finalize.real", case_file_id=case_file_id)
        async with AsyncSessionLocal() as audit_session:
            bd = await bill_detective.run(
                case_file_id, mode="diagnose", confirmations=confirmations, session=audit_session
            )
            log.info("orchestrator.finalize.bd_done", case_file_id=case_file_id, usage=bd.usage)
            mp = await math_person.run(case_file_id, session=audit_session)
            log.info("orchestrator.finalize.mp_done", case_file_id=case_file_id, usage=mp.usage)
            lp = await lead_planner.compose_final(
                case_file_id, bd.final_text, mp.final_text, session=audit_session
            )
            log.info(
                "orchestrator.finalize.lp_done",
                case_file_id=case_file_id,
                usage=lp.usage,
                human_review_needed=lp.human_review_needed,
            )
            await audit_session.commit()
        composed = lp.final_text
    else:
        log.info("orchestrator.finalize.fixture", case_file_id=case_file_id)
        await _persist_mri_fixture_finding(case_file_id)
        composed = mri_audit_fixture(case_file_id).summary

    result = await _assemble_result(case_file_id, composed)
    # Don't mark a degraded (no three-number) result "audit_complete" — that would
    # surface a $0 audit as done (CO-15 T2.3). Reflect the incompleteness.
    terminal = "audit_complete" if result.audit is not None else "audit_incomplete"
    await _set_status(case_file_id, terminal)
    return result
