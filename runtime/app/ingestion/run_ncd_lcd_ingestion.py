"""CMS NCD/LCD ingestion orchestration + CLI (Phase CO-2A).

Pipeline per policy: fetch document → extract_policy → chunk_policy →
embed_and_upsert (payer_policies, payer='CMS'). Idempotent (stable point ids).

Fetchers are injectable so tests drive the whole pipeline from fixtures with no
network; the CLI / cron use the real CMS fetchers by default.

CLI:
  uv run python -m app.ingestion.run_ncd_lcd_ingestion --mode full
  uv run python -m app.ingestion.run_ncd_lcd_ingestion --mode incremental
  uv run python -m app.ingestion.run_ncd_lcd_ingestion --mode sample
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.cms_ingestion_state import CmsIngestionState
from app.ingestion import cms_ncd_lcd as mcd
from app.ingestion.chunk_policy import chunk_policy, embed_and_upsert
from app.ingestion.cms_ncd_lcd import (
    LcdDocument,
    LcdSummary,
    NcdDocument,
    NcdSummary,
    diff_since,
)
from app.ingestion.extract_policy import extract_policy

log = structlog.get_logger(__name__)

# Starting LCD state set. NOT a ceiling — expands in waves per DL-58.
DEFAULT_LCD_STATES = ["CA"]
SAMPLE_LIMIT = 5

NcdIndexFetcher = Callable[[], Awaitable[list[NcdSummary]]]
LcdIndexFetcher = Callable[[str | None], Awaitable[list[LcdSummary]]]
NcdDocFetcher = Callable[[str], Awaitable[NcdDocument]]
LcdDocFetcher = Callable[[str], Awaitable[LcdDocument]]


@dataclass
class PolicyResult:
    policy_id: str
    ok: bool
    chunks: int = 0
    error: str | None = None


@dataclass
class IngestionReport:
    results: list[PolicyResult] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    @property
    def chunks_upserted(self) -> int:
        return sum(r.chunks for r in self.results)


async def ingest_document(document: NcdDocument | LcdDocument) -> int:
    """extract → chunk → embed → upsert one parsed document. Returns chunk count."""
    extracted = await extract_policy(document)
    chunks = chunk_policy(extracted, document)
    return await embed_and_upsert(chunks)


async def _ingest_ncd(summary: NcdSummary, fetch_doc: NcdDocFetcher) -> PolicyResult:
    pid = f"NCD-{summary.ncd_id}"
    try:
        doc = await fetch_doc(summary.ncd_id)
        n = await ingest_document(doc)
        return PolicyResult(pid, True, n)
    except Exception as e:  # noqa: BLE001 — per-policy isolation; one failure can't abort the run
        log.warning("ingestion.ncd_failed", ncd_id=summary.ncd_id, error=str(e))
        return PolicyResult(pid, False, 0, str(e))


async def _ingest_lcd(summary: LcdSummary, fetch_doc: LcdDocFetcher) -> PolicyResult:
    pid = f"LCD-{summary.lcd_id}"
    try:
        doc = await fetch_doc(summary.lcd_id)
        n = await ingest_document(doc)
        return PolicyResult(pid, True, n)
    except Exception as e:  # noqa: BLE001
        log.warning("ingestion.lcd_failed", lcd_id=summary.lcd_id, error=str(e))
        return PolicyResult(pid, False, 0, str(e))


async def run_full_ingestion(
    *,
    fetch_ncd_index: NcdIndexFetcher = mcd.fetch_ncd_index,
    fetch_lcd_index: LcdIndexFetcher = mcd.fetch_lcd_index,
    fetch_ncd_document: NcdDocFetcher = mcd.fetch_ncd_document,
    fetch_lcd_document: LcdDocFetcher = mcd.fetch_lcd_document,
    states: list[str] | None = None,
) -> IngestionReport:
    """One-time full ingestion of all NCDs + all LCDs (optionally state-scoped)."""
    report = IngestionReport()
    for s in await fetch_ncd_index():
        report.results.append(await _ingest_ncd(s, fetch_ncd_document))
    for st in states or [None]:  # None => the index's full LCD set
        for s in await fetch_lcd_index(st):
            report.results.append(await _ingest_lcd(s, fetch_lcd_document))
    log.info("ingestion.full_done", **_summary(report))
    return report


async def run_sample_ingestion(
    *,
    fetch_ncd_index: NcdIndexFetcher = mcd.fetch_ncd_index,
    fetch_lcd_index: LcdIndexFetcher = mcd.fetch_lcd_index,
    fetch_ncd_document: NcdDocFetcher = mcd.fetch_ncd_document,
    fetch_lcd_document: LcdDocFetcher = mcd.fetch_lcd_document,
) -> IngestionReport:
    """5 NCDs + 5 California LCDs — local testing without overwhelming CMS/Qdrant."""
    report = IngestionReport()
    for s in (await fetch_ncd_index())[:SAMPLE_LIMIT]:
        report.results.append(await _ingest_ncd(s, fetch_ncd_document))
    for s in (await fetch_lcd_index("CA"))[:SAMPLE_LIMIT]:
        report.results.append(await _ingest_lcd(s, fetch_lcd_document))
    log.info("ingestion.sample_done", **_summary(report))
    return report


async def run_incremental_ingestion(
    since: datetime.datetime | None = None,
    *,
    fetch_ncd_index: NcdIndexFetcher = mcd.fetch_ncd_index,
    fetch_lcd_index: LcdIndexFetcher = mcd.fetch_lcd_index,
    fetch_ncd_document: NcdDocFetcher = mcd.fetch_ncd_document,
    fetch_lcd_document: LcdDocFetcher = mcd.fetch_lcd_document,
    states: list[str] | None = None,
    max_policies: int | None = None,
) -> IngestionReport:
    """Diff-based update: ingest only NCDs/LCDs new or changed since last run.

    Tracks one cms_ingestion_state row per source ('ncd', 'lcd_<state>'). A policy
    is re-ingested when its last_modified post-dates the source's last_indexed_at.
    ``max_policies`` caps work per run (cost-budget guard for the cron); the diff
    state makes the un-processed remainder safe to pick up on the next run.
    """
    report = IngestionReport()

    def room() -> bool:
        return max_policies is None or report.attempted < max_policies

    # NCDs
    ncd_index = await fetch_ncd_index()
    threshold = since or await _last_indexed("ncd")
    last_map = {s.ncd_id: threshold for s in ncd_index} if threshold else {}
    for changed in diff_since(last_map, ncd_index):
        if not room():
            break
        s = next((x for x in ncd_index if x.ncd_id == changed.policy_id), None)
        if s:
            report.results.append(await _ingest_ncd(s, fetch_ncd_document))
    await _record_run("ncd", IngestionReport(list(report.results)))

    # LCDs per state
    for st in states or DEFAULT_LCD_STATES:
        if not room():
            break
        source_id = f"lcd_{st.lower()}"
        lcd_index = await fetch_lcd_index(st)
        threshold = since or await _last_indexed(source_id)
        last_map = {s.lcd_id: threshold for s in lcd_index} if threshold else {}
        before = report.attempted
        for changed in diff_since(last_map, lcd_index):
            if not room():
                break
            s = next((x for x in lcd_index if x.lcd_id == changed.policy_id), None)
            if s:
                report.results.append(await _ingest_lcd(s, fetch_lcd_document))
        await _record_run(source_id, IngestionReport(report.results[before:]))

    if max_policies is not None and report.attempted >= max_policies:
        log.warning(
            "ingestion.capped_by_budget", max_policies=max_policies, attempted=report.attempted
        )
    log.info("ingestion.incremental_done", **_summary(report))
    return report


# --------------------------------------------------------------------------- #
# cms_ingestion_state bookkeeping
# --------------------------------------------------------------------------- #
async def _last_indexed(source_id: str) -> datetime.datetime | None:
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                select(CmsIngestionState).where(CmsIngestionState.source_id == source_id)
            )
        ).scalar_one_or_none()
        return row.last_indexed_at if row else None


async def _record_run(source_id: str, report: IngestionReport) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    err = next((r.error for r in report.results if not r.ok), None)
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
        row.policies_indexed_count = report.succeeded
        if report.failed == 0:
            row.last_successful_run_at = now
            row.last_error = None
            row.last_error_at = None
        else:
            row.last_error = err
            row.last_error_at = now
        await s.commit()


def _summary(report: IngestionReport) -> dict:
    return {
        "attempted": report.attempted,
        "succeeded": report.succeeded,
        "failed": report.failed,
        "chunks": report.chunks_upserted,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
async def _amain(mode: str) -> IngestionReport:
    if mode == "full":
        return await run_full_ingestion()
    if mode == "incremental":
        return await run_incremental_ingestion()
    if mode == "sample":
        return await run_sample_ingestion()
    raise ValueError(f"unknown mode: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CMS NCD/LCD ingestion into payer_policies")
    parser.add_argument("--mode", choices=["full", "incremental", "sample"], default="sample")
    args = parser.parse_args()
    report = asyncio.run(_amain(args.mode))
    print(
        f"[{args.mode}] attempted={report.attempted} succeeded={report.succeeded} "
        f"failed={report.failed} chunks_upserted={report.chunks_upserted}"
    )
    for r in report.results:
        status = "OK " if r.ok else "ERR"
        print(f"  {status} {r.policy_id}: {r.chunks} chunks" + (f" — {r.error}" if r.error else ""))


if __name__ == "__main__":
    main()
