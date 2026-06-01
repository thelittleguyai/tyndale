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


async def ingest_tic_payer(
    payer: str,
    *,
    year: int,
    file_blob_paths: list[str] | None = None,
    index_url: str | None = None,
    blob: BlobStorage | None = None,
    downloader: BulkDownloader | None = None,
    max_files: int | None = None,
    staging: bool = False,
) -> dict:
    """Ingest a Tier-1 payer's in-network files. Tests pass file_blob_paths."""
    blob = blob or BlobStorage()
    if file_blob_paths is None:
        if not index_url:
            raise ValueError("index_url or file_blob_paths required")
        dl = downloader or BulkDownloader(blob)
        entries = await dl.list_index(index_url)
        chosen = entries[:max_files] if max_files else entries
        file_blob_paths = []
        for e in chosen:
            res = await dl.download(e.url, f"tic-mrf/{payer}/{e.filename}")
            file_blob_paths.append(res.blob_path)

    parser = TicMrfParser(payer, year)
    kept = 0
    ghosted = 0
    for path in file_blob_paths:
        records = [r async for r in parser.parse_file(path, blob)]
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
