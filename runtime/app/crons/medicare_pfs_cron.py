"""Medicare PFS ingestion cron (Phase CO-3A). Annually, ~Jan 5 (PFS releases in Jan).

Small files; ~$0 cost. Loads the current year's RVU file → transparency_rates
(source=medicare_pfs, confidence 1.0).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import structlog

from app.crons._cron_util import audit_cron_run
from app.ingestion.medicare_pfs import ingest_medicare_pfs

log = structlog.get_logger(__name__)
# Stdlib logger for the CF-staleness warning (DL-67). Emitted via stdlib (not the
# structlog ConsoleRenderer) so it surfaces in standard log capture + admin-console alerts.
logger = logging.getLogger(__name__)

# Medicare Conversion Factor effective year. CMS publishes a new CF annually (Final Rule,
# ~Nov/Dec). Bump this each January per DL-67. The PFS parser now reads the authoritative CF
# straight from the PPRRVU file's CONV FACTOR column (33.4009 for 2026, confirmed live);
# DEFAULT_CONVERSION_FACTOR is only the fallback when that column is absent.
MEDICARE_CF_EFFECTIVE_YEAR = 2026


def _check_cf_freshness(current_year: int | None = None) -> None:
    """Warn when the hardcoded Medicare CF year is stale vs. the current year (DL-67)."""
    year = current_year if current_year is not None else datetime.now(timezone.utc).year
    if MEDICARE_CF_EFFECTIVE_YEAR != year:
        logger.warning(
            "Medicare CF stale: MEDICARE_CF_EFFECTIVE_YEAR=%s but current year=%s. "
            "Update per DL-67.",
            MEDICARE_CF_EFFECTIVE_YEAR,
            year,
        )


async def run_medicare_pfs_cron(year: int | None = None) -> dict:
    started = datetime.now(timezone.utc)
    yr = year or started.year
    _check_cf_freshness()  # DL-67: warn loudly if the hardcoded CF year is stale
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
