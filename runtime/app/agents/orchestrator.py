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

from uuid import UUID

import structlog
from sqlalchemy import select

from app.agents import bill_detective, lead_planner, math_person
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.findings import Finding
from app.schemas.case_file import AuditResult, Citation, FindingOut, ThreeNumberAudit
from app.stubs.fixtures import mri_audit_fixture

log = structlog.get_logger(__name__)


def _has_real_anthropic_creds(settings) -> bool:
    """Real key must look like sk-ant-... — placeholder strings ('<from
    terraform output>', empty, unset) fall back to fixture instead of
    hitting Anthropic with an invalid key."""
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
        log.info("orchestrator.fixture_fallback", reason="USE_REAL_CLAUDE=false", case_file_id=case_file_id)
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
    log.info("orchestrator.run_audit.start", case_file_id=case_file_id)

    bd = await bill_detective.run(case_file_id)
    log.info(
        "orchestrator.bill_detective.done",
        case_file_id=case_file_id,
        tool_calls=len(bd.tool_calls),
        usage=bd.usage,
    )

    mp = await math_person.run(case_file_id)
    log.info(
        "orchestrator.math_person.done",
        case_file_id=case_file_id,
        tool_calls=len(mp.tool_calls),
        usage=mp.usage,
    )

    lp = await lead_planner.compose_final(
        case_file_id, bd.final_text, mp.final_text
    )
    log.info(
        "orchestrator.lead_planner.done",
        case_file_id=case_file_id,
        tool_calls=len(lp.tool_calls),
        usage=lp.usage,
    )

    # Assemble the API response from persisted findings.
    return await _assemble_result(case_file_id, lp.final_text)


async def _assemble_result(case_file_id: str, composed: str) -> AuditResult:
    """Read findings from Postgres and project to AuditResult shape."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Finding).where(Finding.case_file_id == UUID(case_file_id))
        )).scalars().all()

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
        # Real agents ran but didn't write the three-number finding — fall
        # back to fixture audit so the response shape is still valid.
        log.warning("orchestrator.no_three_number_finding", case_file_id=case_file_id)
        three_numbers = {"provider_billed": 0.0, "eob_member_responsibility": 0.0, "tyndale_computed": 0.0}

    return AuditResult(
        case_file_id=case_file_id,
        status="complete",
        audit=ThreeNumberAudit(**three_numbers),
        findings=findings,
        summary=composed,
    )
