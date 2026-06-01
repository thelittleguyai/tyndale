"""Medicare PFS ingestion cron (Phase CO-3A). Annually, ~Jan 5 (PFS releases in Jan).

Small files; ~$0 cost. Loads the current year's RVU file → transparency_rates
(source=medicare_pfs, confidence 1.0).
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.crons._cron_util import audit_cron_run
from app.ingestion.medicare_pfs import ingest_medicare_pfs

log = structlog.get_logger(__name__)


async def run_medicare_pfs_cron(year: int | None = None) -> dict:
    started = datetime.now(timezone.utc)
    yr = year or started.year
    try:
        n = await ingest_medicare_pfs(yr)
    except Exception as e:  # noqa: BLE001
        log.error("cron.medicare_pfs.failed", year=yr, error=str(e))
        await audit_cron_run(
            "cron:medicare_pfs", "error", {"year": yr, "error": str(e)}, error=str(e)
        )
        raise
    payload = {"phase": "co-3a", "year": yr, "rates_ingested": n, "started_at": started.isoformat()}
    await audit_cron_run("cron:medicare_pfs", "success", payload)
    log.info("cron.medicare_pfs.done", **payload)
    return payload
