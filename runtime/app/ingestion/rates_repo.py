"""Persistence + lookups for transparency_rates (Phase CO-3A).

persist_rates() bulk-inserts RateRecords (live or staging per DL-59).
medicare_baseline_map() + corroboration_count() feed the DL-63 ghost filter +
confidence scoring during TiC ingestion.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable

import structlog
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AsyncSessionLocal
from app.db.models.transparency_rates import TransparencyRate, TransparencyRateStaging
from app.ingestion.parsers import RateRecord

log = structlog.get_logger(__name__)


def _year() -> int:
    return datetime.date.today().year


async def persist_rates(
    records: list[RateRecord],
    *,
    confidence_fn: Callable[[RateRecord], float],
    staging: bool = False,
    session: AsyncSession | None = None,
) -> int:
    """Insert RateRecords into transparency_rates (or _staging per DL-59)."""
    model = TransparencyRateStaging if staging else TransparencyRate
    rows = [
        model(
            source=r.source,
            code=r.code,
            code_type=r.code_type,
            payer=r.payer,
            hospital_id=r.hospital_id,
            location_zip3=r.location_zip3,
            rate=r.rate,
            rate_type=r.rate_type,
            effective_year=r.effective_year or _year(),
            confidence_score=round(max(0.0, min(1.0, confidence_fn(r))), 2),
            raw_metadata=r.raw_metadata or None,
        )
        for r in records
    ]
    if not rows:
        return 0
    if session is not None:
        session.add_all(rows)
        await session.flush()
        return len(rows)
    async with AsyncSessionLocal() as s:
        s.add_all(rows)
        await s.commit()
    return len(rows)


async def medicare_baseline_map(
    codes: list[str], session: AsyncSession | None = None
) -> dict[str, float]:
    """code -> Medicare allowable (national baseline) for the given codes."""
    if not codes:
        return {}

    async def _run(s: AsyncSession) -> dict[str, float]:
        rows = (
            await s.execute(
                select(TransparencyRate.code, TransparencyRate.rate).where(
                    TransparencyRate.source == "medicare_pfs", TransparencyRate.code.in_(codes)
                )
            )
        ).all()
        return {code: float(rate) for code, rate in rows}

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)


async def corroboration_count(code: str, session: AsyncSession | None = None) -> int:
    """How many distinct payers already have a market rate for this code."""

    async def _run(s: AsyncSession) -> int:
        return (
            await s.execute(
                select(func.count(distinct(TransparencyRate.payer))).where(
                    TransparencyRate.code == code,
                    TransparencyRate.source.in_(("hospital_mrf", "tic_mrf")),
                    TransparencyRate.payer.isnot(None),
                )
            )
        ).scalar_one()

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)
