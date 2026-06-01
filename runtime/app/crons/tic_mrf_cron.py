"""TiC MRF ingestion cron (Phase CO-3A). Monthly, first Sunday (TiC updates monthly).

Iterates Tier-1 payers (data/tier1_payer_tic_indices.csv) → ingest each into
transparency_rates with DL-63 ghost filtering. The big one: ~$50-200/run (large
downloads + processing). max_files caps per-payer cost.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.crons._cron_util import audit_cron_run, load_tier1_payer_indices
from app.ingestion.tic_mrf import ingest_tic_payer

log = structlog.get_logger(__name__)

MAX_FILES_PER_PAYER = 50  # cost cap; expansion is Sprint C+ (DL-58)


async def run_tic_mrf_cron(year: int | None = None) -> dict:
    started = datetime.now(timezone.utc)
    yr = year or started.year
    payers = load_tier1_payer_indices()
    kept = 0
    ghosted = 0
    failed = 0
    for p in payers:
        try:
            res = await ingest_tic_payer(
                p["payer"],
                year=yr,
                index_url=p.get("index_url"),
                max_files=MAX_FILES_PER_PAYER,
            )
            kept += res["kept"]
            ghosted += res["ghosted"]
        except Exception as e:  # noqa: BLE001 — per-payer isolation
            log.warning("cron.tic_mrf.one_failed", payer=p.get("payer"), error=str(e))
            failed += 1
    payload = {
        "phase": "co-3a",
        "started_at": started.isoformat(),
        "year": yr,
        "rates_kept": kept,
        "rates_ghosted": ghosted,
        "payers_failed": failed,
    }
    if failed:
        log.warning("cron.tic_mrf.partial", **payload)
    await audit_cron_run("cron:tic_mrf", "success" if not failed else "error", payload)
    log.info("cron.tic_mrf.done", **payload)
    return payload
