"""TiC MRF ingestion (Phase CO-3A) — Tier-1 commercial payers + ghost filtering.

Reads index_url per payer from data/tier1_payer_tic_indices.csv. Each surviving
rate (DL-63 ghost filter) gets a confidence_score. Streams files so a multi-GB
in-network file never fully loads.

Cold-start note (DL-63): the corroboration criterion ("present in ≥2 payer files")
means the FIRST payer ingested into a fresh DB will have most rates filtered as
single-occurrence — corroboration accumulates as more Tier-1 payers load. The
realistic flow loads all Tier-1 payers, then the surviving set stabilizes.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json

import httpx
import structlog

from app.ingestion.blob_storage import BlobStorage
from app.ingestion.bulk_download import BulkDownloader
from app.ingestion.ghost_rate_filter import confidence_score, is_likely_ghost
from app.ingestion.parsers.tic_mrf import TicMrfParser
from app.ingestion.rates_repo import (
    corroboration_count,
    medicare_baseline_map,
    persist_rates,
)

log = structlog.get_logger(__name__)

_UA = "Mozilla/5.0 (compatible; TyndaleBot/0.1; +https://tyndaleapp.net)"
# TiC in-network files are routinely multi-GB; skip oversized ones in the (bounded) sample.
TIC_SAMPLE_MAX_BYTES = 200_000_000
# Cap rates persisted per in-network file in sample mode.
SAMPLE_RECORD_LIMIT = 500


def parse_tic_toc(raw: bytes) -> list[tuple[str, str]]:
    """Parse a CMS TiC table-of-contents JSON -> [(description, in_network_file_url)].

    CMS schema: ``reporting_structure[].in_network_files[].{description, location}``. Some
    payers ship a flat ``{in_network_files: [...]}`` index; gzip is handled transparently.
    This replaces the HTML ``list_index`` for TiC — the TOC is JSON, never an HTML page.
    """
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    doc = json.loads(raw.decode("utf-8", errors="replace"))
    out: list[tuple[str, str]] = []
    for struct in doc.get("reporting_structure") or []:
        for f in struct.get("in_network_files") or []:
            if isinstance(f, dict) and f.get("location"):
                out.append((f.get("description") or "", f["location"]))
    if not out:  # flat-index fallback
        for f in doc.get("in_network_files") or []:
            if isinstance(f, dict) and f.get("location"):
                out.append((f.get("description") or "", f["location"]))
    return out


async def ingest_tic_payer(
    payer: str,
    *,
    year: int,
    file_blob_paths: list[str] | None = None,
    index_url: str | None = None,
    index_blob_path: str | None = None,
    blob: BlobStorage | None = None,
    downloader: BulkDownloader | None = None,
    max_files: int | None = None,
    max_bytes: int | None = TIC_SAMPLE_MAX_BYTES,
    record_limit: int | None = None,
    staging: bool = False,
) -> dict:
    """Ingest a Tier-1 payer's in-network files.

    Resolves the in-network file URLs from the payer's TiC table-of-contents JSON (the CMS
    ``reporting_structure[].in_network_files[].location`` schema) — NOT an HTML index. Tests
    pass file_blob_paths (skip all I/O) or index_blob_path (skip only the TOC download).
    ``max_bytes`` skips oversized in-network files (full ingest needs true HTTP streaming).
    """
    blob = blob or BlobStorage()
    if file_blob_paths is None:
        dl = downloader or BulkDownloader(blob)
        if index_blob_path is None:
            if not index_url:
                raise ValueError("index_url, index_blob_path, or file_blob_paths required")
            res = await dl.download(index_url, f"tic-mrf/{payer}/toc.json")
            index_blob_path = res.blob_path
        locations = parse_tic_toc(await blob.read_bytes(index_blob_path))
        chosen = locations[:max_files] if max_files else locations
        file_blob_paths = []
        for i, (_desc, url) in enumerate(chosen):
            if max_bytes:
                try:
                    async with httpx.AsyncClient(
                        follow_redirects=True, timeout=60.0, headers={"User-Agent": _UA}
                    ) as probe:
                        size = int((await probe.head(url)).headers.get("content-length") or 0)
                except Exception:  # noqa: BLE001 — HEAD is best-effort; fall through
                    size = 0
                if size > max_bytes:
                    log.warning("tic_mrf.skipped_large", payer=payer, url=url[:120], size=size)
                    continue
            res = await dl.download(url, f"tic-mrf/{payer}/innetwork_{i}.json")
            file_blob_paths.append(res.blob_path)

    parser = TicMrfParser(payer, year)
    kept = 0
    ghosted = 0
    for path in file_blob_paths:
        records = []
        async for r in parser.parse_file(path, blob):
            records.append(r)
            if record_limit and len(records) >= record_limit:
                break
        if not records:
            continue
        baseline = await medicare_baseline_map(sorted({r.code for r in records}))
        conf_by_id: dict[int, float] = {}
        survivors = []
        for r in records:
            corr = (await corroboration_count(r.code)) + 1
            mb = baseline.get(r.code)
            if is_likely_ghost(r.rate, mb, corr):
                ghosted += 1
                continue
            conf_by_id[id(r)] = confidence_score(r.rate, mb, corr, 0)
            survivors.append(r)
        kept += await persist_rates(
            survivors, confidence_fn=lambda r: conf_by_id.get(id(r), 0.5), staging=staging
        )

    log.info("tic_mrf.ingested", payer=payer, kept=kept, ghosted=ghosted)
    return {"payer": payer, "kept": kept, "ghosted": ghosted}


async def _run_sample(payer: str | None, limit: int, year: int) -> dict:
    """Ingest one Tier-1 payer's first ``limit`` in-network files via its TiC TOC.

    NOTE (CO-3A): the JSON-TOC parser + size/record guards are in place, but the starter
    tier1_payer_tic_indices.csv still holds payer *landing pages*, not direct TOC-JSON URLs
    (payers gate those behind JS pages / dated CDN keys, and the files are multi-GB). A live
    run needs a real TOC-JSON index_url; with a landing page this reports the parse error
    cleanly rather than crash.
    """
    from app.crons._cron_util import load_tier1_payer_indices

    rows = load_tier1_payer_indices()
    if payer:
        rows = [r for r in rows if payer.lower() in r.get("payer", "").lower()]
    if not rows:
        return {"error": f"payer {payer!r} not found in tier1_payer_tic_indices.csv"}
    row = rows[0]
    try:
        return await ingest_tic_payer(
            row["payer"],
            year=year,
            index_url=row.get("index_url"),
            max_files=limit,
            record_limit=SAMPLE_RECORD_LIMIT,
            staging=False,
        )
    except Exception as e:  # noqa: BLE001 — report the real-source gap, don't crash
        return {"payer": row["payer"], "error": f"{type(e).__name__}: {str(e)[:160]}"}


def main() -> None:
    p = argparse.ArgumentParser(description="TiC MRF ingestion into transparency_rates")
    p.add_argument("--mode", choices=["sample", "full"], default="sample")
    p.add_argument("--limit", type=int, default=1, help="max in-network files to pull (cost guard)")
    p.add_argument(
        "--payer", type=str, default=None, help="substring match on the CSV payer column"
    )
    p.add_argument("--year", type=int, default=2026)
    args = p.parse_args()
    rep = asyncio.run(_run_sample(args.payer, args.limit, args.year))
    print(f"[tic_mrf {args.mode}] {rep}")


if __name__ == "__main__":
    main()
