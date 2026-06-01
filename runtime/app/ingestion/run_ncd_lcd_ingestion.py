"""CMS NCD/LCD bulk ingestion orchestration + CLI (CO-2A.1).

Thin wrapper over cms_ncd_lcd.ingest_from_bulk() (the real bulk-download path).
run_incremental records progress in cms_ingestion_state; the BulkDownloader's
Last-Modified cache makes re-runs idempotent (unchanged ZIP → 0 work).

CLI:
  uv run python -m app.ingestion.run_ncd_lcd_ingestion --mode full
  uv run python -m app.ingestion.run_ncd_lcd_ingestion --mode incremental
  uv run python -m app.ingestion.run_ncd_lcd_ingestion --mode sample
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
from typing import Any

import structlog
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.cms_ingestion_state import CmsIngestionState
from app.ingestion import cms_ncd_lcd as mcd

log = structlog.get_logger(__name__)

SAMPLE_LIMIT = 10
_SOURCE_ID = "ncd_lcd_bulk"


async def run_full_ingestion(**kwargs: Any) -> dict:
    return await mcd.ingest_from_bulk(**kwargs)


async def run_sample_ingestion(**kwargs: Any) -> dict:
    return await mcd.ingest_from_bulk(sample_limit=SAMPLE_LIMIT, **kwargs)


async def run_incremental_ingestion(max_policies: int | None = None, **kwargs: Any) -> dict:
    """Re-ingest (the downloader skips an unchanged ZIP). ``max_policies`` caps
    work per run (cost-budget guard for the cron)."""
    report = await mcd.ingest_from_bulk(sample_limit=max_policies, **kwargs)
    await _record_run(_SOURCE_ID, report)
    return report


async def _record_run(source_id: str, report: dict) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    err = next((r.get("error") for r in report.get("results", []) if not r.get("ok")), None)
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CmsIngestionState).where(CmsIngestionState.source_id == source_id)
            )
        ).scalar_one_or_none()
        if row is None:
            row = CmsIngestionState(source_id=source_id, last_indexed_at=now)
            s.add(row)
        row.last_indexed_at = now
        row.policies_indexed_count = report.get("succeeded", 0)
        if report.get("failed", 0) == 0:
            row.last_successful_run_at = now
            row.last_error = None
            row.last_error_at = None
        else:
            row.last_error = err
            row.last_error_at = now
        await s.commit()


async def _amain(mode: str) -> dict:
    if mode == "full":
        return await run_full_ingestion()
    if mode == "incremental":
        return await run_incremental_ingestion()
    if mode == "sample":
        return await run_sample_ingestion()
    raise ValueError(f"unknown mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CMS NCD/LCD bulk ingestion into payer_policies")
    parser.add_argument("--mode", choices=["full", "incremental", "sample"], default="sample")
    args = parser.parse_args()
    rep = asyncio.run(_amain(args.mode))
    print(
        f"[{args.mode}] attempted={rep['attempted']} succeeded={rep['succeeded']} "
        f"failed={rep['failed']} chunks_upserted={rep['chunks_upserted']}"
    )


if __name__ == "__main__":
    main()
