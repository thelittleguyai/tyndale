"""Weekly CMS NCD/LCD ingestion cron (Phase CO-2A · Option B — dedicated cron).

WHY OPTION B (dedicated cron, not "extend the Regulation Researcher cron"): there
is no Regulation Researcher cron in the codebase yet — outcome_followup.py is the
only cron and is a standalone one-module-per-cron file. A dedicated module matches
that existing shape and keeps CMS ingestion isolated. When the broader Regulation
Researcher lands (Phase 5, developer-spec §10), it can simply call
run_cms_ncd_lcd_cron() as one of its scheduled tasks.

SCHEDULE: weekly, Sundays 03:00 UTC (developer-spec §10). The Container Apps Job +
cron-schedule wiring lands with infra (same migrations-in-CI pattern as DL-31);
like outcome_followup, V1-Lite ships the callable here and the scheduler arrives
with the infra phase. This module is the entry point the job will invoke (it also
backs `run_ncd_lcd_ingestion --mode incremental`).

Per developer-spec §10 this cron: enforces a cost budget per run, routes failure
alerts to ops (not users), logs every run to the audit stream, and is idempotent
by design (diff-driven discovery + stable Qdrant point ids).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import structlog

from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.ingestion.run_ncd_lcd_ingestion import IngestionReport, run_incremental_ingestion

log = structlog.get_logger(__name__)

# Cost budget per weekly run. Claude extraction dominates cost; ~$0.02/policy is a
# conservative estimate for a single ~2k-token sonnet extraction at standard
# pricing (DL-62). The budget caps policies-per-run so a large MCD drop can't
# overspend in one week — the remainder is picked up the following week (the diff
# state makes that safe). Refine the estimate once real spend is measured.
COST_BUDGET_USD = 5.0
EST_COST_PER_POLICY_USD = 0.02
MAX_POLICIES_PER_RUN = int(COST_BUDGET_USD / EST_COST_PER_POLICY_USD)  # 250


async def run_cms_ncd_lcd_cron() -> IngestionReport:
    """Run one weekly incremental CMS ingestion, budgeted + audited."""
    started = datetime.now(timezone.utc)
    try:
        report = await run_incremental_ingestion(max_policies=MAX_POLICIES_PER_RUN)
    except Exception as e:  # noqa: BLE001 — alert ops, audit, re-raise so the job is marked failed
        log.error("cron.cms_ingestion.failed", error=str(e))  # ops alert (Phase 4: pager/webhook)
        await _audit(
            "error",
            {"phase": "co-2a", "started_at": started.isoformat(), "error": str(e)},
            error=str(e),
        )
        raise

    est_cost = round(report.succeeded * EST_COST_PER_POLICY_USD, 4)
    payload = {
        "phase": "co-2a",
        "started_at": started.isoformat(),
        "attempted": report.attempted,
        "succeeded": report.succeeded,
        "failed": report.failed,
        "chunks_upserted": report.chunks_upserted,
        "estimated_cost_usd": est_cost,
        "cost_budget_usd": COST_BUDGET_USD,
        "max_policies_per_run": MAX_POLICIES_PER_RUN,
    }
    if report.failed:
        log.warning("cron.cms_ingestion.partial_failure", **payload)  # ops alert
    if report.attempted >= MAX_POLICIES_PER_RUN:
        # Budget cap hit — remainder resumes next run (diff state makes this safe).
        log.warning("cron.cms_ingestion.budget_cap_reached", **payload)
    await _audit(
        "success" if not report.failed else "error",
        payload,
        error=next((r.error for r in report.results if not r.ok), None),
    )
    log.info("cron.cms_ingestion.done", **payload)
    return report


async def _audit(outcome: str, payload: dict, error: str | None = None) -> None:
    body = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    async with AsyncSessionLocal() as s:
        s.add(
            AuditEvent(
                event_type="system_action",
                actor="cron:cms_ncd_lcd",
                case_file_id=None,
                payload_encrypted=body,  # TODO(Phase 4): AES-GCM via Key Vault
                payload_hash=hashlib.sha256(body).digest(),
                key_version=0,
                tools_invoked=["cms_ncd_lcd_ingestion"],
                outcome=outcome,
                error_details=error,
            )
        )
        await s.commit()
