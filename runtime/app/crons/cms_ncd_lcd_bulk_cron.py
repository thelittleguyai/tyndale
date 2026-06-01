"""Weekly CMS NCD/LCD BULK ingestion cron (CO-2A.1). Replaces the old JSON-API cron.

Schedule: weekly, Sundays 03:00 UTC (developer-spec §10). Container Apps Job
pattern (DL-31); no scheduler wired in V1-Lite — manual trigger / follow-on infra.
Budget: MAX_POLICIES_PER_RUN caps Claude extraction cost; the remainder resumes
next run. Idempotent: the BulkDownloader skips an unchanged ZIP.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.crons._cron_util import audit_cron_run
from app.ingestion.run_ncd_lcd_ingestion import run_incremental_ingestion

log = structlog.get_logger(__name__)

COST_BUDGET_USD = 5.0
EST_COST_PER_POLICY_USD = 0.02
MAX_POLICIES_PER_RUN = int(COST_BUDGET_USD / EST_COST_PER_POLICY_USD)  # 250


async def run_cms_ncd_lcd_bulk_cron() -> dict:
    started = datetime.now(timezone.utc)
    try:
        report = await run_incremental_ingestion(max_policies=MAX_POLICIES_PER_RUN)
    except Exception as e:  # noqa: BLE001 — alert ops, audit, re-raise
        log.error("cron.cms_bulk.failed", error=str(e))
        await audit_cron_run(
            "cron:cms_ncd_lcd_bulk",
            "error",
            {"started_at": started.isoformat(), "error": str(e)},
            error=str(e),
        )
        raise
    payload = {
        "phase": "co-2a.1",
        "started_at": started.isoformat(),
        "attempted": report["attempted"],
        "succeeded": report["succeeded"],
        "failed": report["failed"],
        "chunks_upserted": report["chunks_upserted"],
        "max_policies_per_run": MAX_POLICIES_PER_RUN,
    }
    if report["failed"]:
        log.warning("cron.cms_bulk.partial", **payload)
    await audit_cron_run(
        "cron:cms_ncd_lcd_bulk", "success" if not report["failed"] else "error", payload
    )
    log.info("cron.cms_bulk.done", **payload)
    return report
