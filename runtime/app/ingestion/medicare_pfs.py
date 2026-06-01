"""Medicare PFS ingestion (Phase CO-3A) — download → parse → transparency_rates.

Real source page (live 2026-05-30):
cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files — a
per-year ZIP with a PPRRVU CSV. The exact ZIP link is year-specific, discovered
from the page index. Medicare is the baseline source: confidence_score = 1.0.
"""

from __future__ import annotations

import zipfile

import structlog

from app.ingestion.blob_storage import BlobStorage
from app.ingestion.bulk_download import BulkDownloader
from app.ingestion.parsers.medicare_pfs import DEFAULT_CONVERSION_FACTOR, MedicarePfsParser
from app.ingestion.rates_repo import persist_rates

log = structlog.get_logger(__name__)

PFS_PAGE = "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files"


async def _extract_pprrvu_csv(zip_blob_path: str, blob: BlobStorage, year: int) -> str:
    path = await blob.materialize_local(zip_blob_path)
    out_blob = f"medicare-pfs/{year}/pprrvu.csv"
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        csv_name = next(
            (n for n in names if "pprrvu" in n.lower() and n.lower().endswith(".csv")), None
        )
        csv_name = csv_name or next((n for n in names if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise RuntimeError(f"no CSV found inside PFS zip {zip_blob_path}")
        await blob.write_bytes(out_blob, zf.read(csv_name))
    return out_blob


async def ingest_medicare_pfs(
    year: int,
    *,
    csv_blob_path: str | None = None,
    blob: BlobStorage | None = None,
    downloader: BulkDownloader | None = None,
    source_url: str | None = None,
    conversion_factor: float = DEFAULT_CONVERSION_FACTOR,
    staging: bool = False,
) -> int:
    """Ingest the year's PFS allowables. Tests pass csv_blob_path to skip download."""
    blob = blob or BlobStorage()
    if csv_blob_path is None:
        dl = downloader or BulkDownloader(blob)
        if source_url is None:
            # VERIFY at impl time: pick the year's RVU zip from the page index.
            entries = await dl.list_index(PFS_PAGE)
            match = next(
                (
                    e
                    for e in entries
                    if str(year) in e.filename and e.filename.lower().endswith(".zip")
                ),
                None,
            )
            if match is None:
                raise RuntimeError(f"could not find {year} PFS RVU zip on {PFS_PAGE}")
            source_url = match.url
        res = await dl.download(source_url, f"medicare-pfs/{year}/rvu.zip")
        csv_blob_path = await _extract_pprrvu_csv(res.blob_path, blob, year)

    parser = MedicarePfsParser(year, conversion_factor)
    records = [r async for r in parser.parse_file(csv_blob_path, blob)]
    n = await persist_rates(records, confidence_fn=lambda r: 1.0, staging=staging)
    log.info("medicare_pfs.ingested", year=year, rates=n)
    return n
