"""Hospital MRF ingestion (Phase CO-3A) — top-100 hospital negotiated rates.

Reads mrf_url per hospital from data/top_100_hospitals.csv. Per DL-59 new
hospitals land in transparency_rates_staging first (staging=True default);
promotion to live requires a ≥90% extraction-confidence sample. Hospital data is
direct (the hospital's own published file), so no ghost filter — confidence
reflects format completeness. Cost cap: the whole top-100 batch fits one run;
expansion past 100 is Sprint C+ (DL-58).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime

import structlog

from app.ingestion.blob_storage import BlobStorage
from app.ingestion.bulk_download import BulkDownloader
from app.ingestion.parsers.hospital_mrf import HospitalMrfParser
from app.ingestion.rates_repo import persist_rates

log = structlog.get_logger(__name__)


async def ingest_hospital_mrf(
    hospital_id: str,
    mrf_url: str | None = None,
    *,
    hospital_zip3: str | None = None,
    year: int | None = None,
    blob: BlobStorage | None = None,
    downloader: BulkDownloader | None = None,
    blob_path: str | None = None,
    staging: bool = True,
) -> int:
    """Ingest one hospital's MRF. Tests pass blob_path to skip download."""
    blob = blob or BlobStorage()
    if blob_path is None:
        if not mrf_url:
            raise ValueError("mrf_url or blob_path required")
        dl = downloader or BulkDownloader(blob)
        res = await dl.download(mrf_url, f"hospital-mrf/{hospital_id}/mrf.json")
        blob_path = res.blob_path

    yr = year or datetime.date.today().year
    records = []
    async for r in HospitalMrfParser(hospital_id).parse_file(blob_path, blob):
        r.location_zip3 = hospital_zip3
        r.effective_year = yr
        records.append(r)

    n = await persist_rates(records, confidence_fn=lambda r: 0.85, staging=staging)
    log.info("hospital_mrf.ingested", hospital_id=hospital_id, rates=n, staging=staging)
    return n


async def _run_sample(limit: int) -> dict:
    """Ingest the first ``limit`` hospitals from top_100_hospitals.csv (DL-59 staging).

    NOTE (CO-3A real-source gap): the starter CSV holds landing-page URLs, not direct
    MRF JSON, so these will fail until real per-hospital MRF URLs are curated.
    """
    from app.crons._cron_util import load_top_100_hospitals

    hospitals = load_top_100_hospitals()[:limit]
    ok = failed = total = 0
    errors: list[str] = []
    for h in hospitals:
        try:
            n = await ingest_hospital_mrf(
                h["hospital_id"], h.get("mrf_url"), hospital_zip3=h.get("zip3"), staging=True
            )
            total += n
            ok += 1
        except Exception as e:  # noqa: BLE001 — per-hospital isolation; report, don't abort
            failed += 1
            errors.append(
                f"{h.get('hospital_id')} ({h.get('hospital_name')}): "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
    return {"ok": ok, "failed": failed, "rates": total, "errors": errors}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Hospital MRF ingestion into transparency_rates_staging"
    )
    p.add_argument("--mode", choices=["sample", "full"], default="sample")
    p.add_argument("--limit", type=int, default=2, help="number of hospitals from the CSV")
    args = p.parse_args()
    rep = asyncio.run(_run_sample(args.limit))
    print(
        f"[hospital_mrf {args.mode}] ok={rep['ok']} failed={rep['failed']} "
        f"rates_staged={rep['rates']}"
    )
    for e in rep["errors"]:
        print("   FAIL", e)


if __name__ == "__main__":
    main()
