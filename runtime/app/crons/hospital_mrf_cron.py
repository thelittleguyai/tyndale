"""Hospital MRF ingestion cron (Phase CO-3A). Monthly, first Sunday.

Iterates the top-100 hospitals (data/top_100_hospitals.csv) → ingest each into
transparency_rates_staging (DL-59). Cost cap: the whole batch is one run; expansion
past 100 is Sprint C+ (DL-58). ~$5-20/run (storage + compute).
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.crons._cron_util import audit_cron_run, load_top_100_hospitals
from app.ingestion.hospital_mrf import ingest_hospital_mrf

log = structlog.get_logger(__name__)

MAX_HOSPITALS_PER_RUN = 100


async def run_hospital_mrf_cron() -> dict:
    started = datetime.now(timezone.utc)
    hospitals = load_top_100_hospitals()[:MAX_HOSPITALS_PER_RUN]
    ok = 0
    failed = 0
    total_rates = 0
    for h in hospitals:
        try:
            n = await ingest_hospital_mrf(
                h["hospital_id"],
                h.get("mrf_url"),
                hospital_zip3=h.get("zip3"),
                staging=True,  # DL-59: land in staging first
            )
            total_rates += n
            ok += 1
        except Exception as e:  # noqa: BLE001 — per-hospital isolation
            log.warning(
                "cron.hospital_mrf.one_failed", hospital_id=h.get("hospital_id"), error=str(e)
            )
            failed += 1
    payload = {
        "phase": "co-3a",
        "started_at": started.isoformat(),
        "hospitals_ok": ok,
        "hospitals_failed": failed,
        "rates_staged": total_rates,
    }
    if failed:
        log.warning("cron.hospital_mrf.partial", **payload)
    await audit_cron_run("cron:hospital_mrf", "success" if not failed else "error", payload)
    log.info("cron.hospital_mrf.done", **payload)
    return payload
