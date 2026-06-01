"""Hospital MRF ingestion (Phase CO-3A) — top-100 hospital negotiated rates.

Reads mrf_url per hospital from data/top_100_hospitals.csv. Per DL-59 new
hospitals land in transparency_rates_staging first (staging=True default);
promotion to live requires a ≥90% extraction-confidence sample. Hospital data is
direct (the hospital's own published file), so no ghost filter — confidence
reflects format completeness. Cost cap: the whole top-100 batch fits one run;
expansion past 100 is Sprint C+ (DL-58).
"""

from __future__ import annotations

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
