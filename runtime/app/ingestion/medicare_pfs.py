"""Medicare PFS ingestion (Phase CO-3A) — download → parse → transparency_rates.

Real source page (live 2026-05-30):
cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files — a
per-year ZIP with a PPRRVU CSV. The exact ZIP link is year-specific, discovered
from the page index. Medicare is the baseline source: confidence_score = 1.0.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import zipfile
from urllib.parse import urljoin

import httpx
import structlog

from app.ingestion.blob_storage import BlobStorage
from app.ingestion.bulk_download import BulkDownloader
from app.ingestion.parsers.medicare_pfs import DEFAULT_CONVERSION_FACTOR, MedicarePfsParser
from app.ingestion.rates_repo import persist_rates

log = structlog.get_logger(__name__)

PFS_PAGE = "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files"
_UA = "Mozilla/5.0 (compatible; TyndaleBot/0.1; +https://tyndaleapp.net)"


async def discover_pfs_zip_url(
    year: int, *, release: str = "a", client: httpx.AsyncClient | None = None
) -> str:
    """Two-hop discovery of the real RVU zip URL (CO-3A real-source fix).

    The PFS index page does NOT link zips directly — it links per-release *item*
    pages (anchor text e.g. ``RVU26A`` -> ``.../pfs-relative-value-files/rvu26a``),
    and the item page holds the actual ``/files/zip/rvu26a-updated-MM-DD-YYYY.zip``
    link. The date suffix changes each release, so the zip URL must be discovered,
    not hardcoded. ``release`` picks the annual file: 'a' = initial full-year,
    'b'/'c'/'d' = later quarterly updates that supersede it.
    """
    name = f"RVU{year % 100:02d}{release.upper()}"
    own_client = client is None
    client = client or httpx.AsyncClient(
        follow_redirects=True, timeout=30.0, headers={"User-Agent": _UA}
    )
    try:
        index_html = (await client.get(PFS_PAGE)).text
        pairs = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>', index_html, re.I)
        item_href = next((h for h, text in pairs if text.strip().upper() == name), None)
        if item_href is None:
            raise RuntimeError(f"PFS index {PFS_PAGE} has no {name} release link")
        item_url = urljoin(PFS_PAGE, item_href)
        item_html = (await client.get(item_url)).text
        zip_match = re.search(r'href="([^"]+\.zip[^"]*)"', item_html, re.I)
        if zip_match is None:
            raise RuntimeError(f"PFS item page {item_url} has no .zip download link")
        return urljoin(item_url, zip_match.group(1))
    finally:
        if own_client:
            await client.aclose()


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
    record_limit: int | None = None,
    staging: bool = False,
) -> int:
    """Ingest the year's PFS allowables. Tests pass csv_blob_path to skip download;
    ``record_limit`` caps persisted rows (sample mode)."""
    blob = blob or BlobStorage()
    if csv_blob_path is None:
        dl = downloader or BulkDownloader(blob)
        if source_url is None:
            source_url = await discover_pfs_zip_url(year)
        res = await dl.download(source_url, f"medicare-pfs/{year}/rvu.zip")
        csv_blob_path = await _extract_pprrvu_csv(res.blob_path, blob, year)

    parser = MedicarePfsParser(year, conversion_factor)
    records = [r async for r in parser.parse_file(csv_blob_path, blob)]
    if record_limit is not None:
        records = records[:record_limit]
    n = await persist_rates(records, confidence_fn=lambda r: 1.0, staging=staging)
    log.info("medicare_pfs.ingested", year=year, rates=n)
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="Medicare PFS ingestion into transparency_rates")
    p.add_argument("--mode", choices=["full", "sample"], default="sample")
    p.add_argument("--limit", type=int, default=5, help="sample mode: max rate rows to persist")
    p.add_argument("--year", type=int, default=2026)
    args = p.parse_args()
    limit = args.limit if args.mode == "sample" else None
    n = asyncio.run(ingest_medicare_pfs(args.year, record_limit=limit))
    print(f"[medicare_pfs {args.mode}] year={args.year} rates_persisted={n}")


if __name__ == "__main__":
    main()
