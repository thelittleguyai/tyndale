"""Cost-estimation query layer (Phase CO-3A, CO-002 Item 3).

estimate_cost() combines all available transparency_rates for a code+location
into a CONFIDENCE-BANDED estimate — NEVER a point number (No Surprises Act
good-faith-estimate framing). Medicare PFS is the always-available baseline;
hospital_mrf + tic_mrf negotiated rates refine it when present. source='trilliant'
is skipped until that adapter is real (DL-50).

DL-54: this layer returns code NUMBERS + dollar bands only — it never emits a CPT
descriptor. User-facing copy maps the code to a placeholder ("MRI of the head").
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transparency_rates import TransparencyRate

log = structlog.get_logger(__name__)

_BASELINE_BAND = Decimal("0.35")  # ±35% band when only the Medicare baseline exists
_MARKET_SOURCES = ("hospital_mrf", "tic_mrf")


@dataclass
class CostEstimate:
    code: str
    location_zip3: str | None
    central_estimate: Decimal | None
    low_estimate: Decimal | None  # 25th percentile (or band floor)
    high_estimate: Decimal | None  # 75th percentile (or band ceiling)
    sources_used: list[str] = field(default_factory=list)
    confidence_summary: str = ""
    methodology: str = ""

    def to_dict(self) -> dict:
        def d(x: Decimal | None) -> float | None:
            return float(x) if x is not None else None

        return {
            "code": self.code,
            "location_zip3": self.location_zip3,
            "central_estimate": d(self.central_estimate),
            "low_estimate": d(self.low_estimate),
            "high_estimate": d(self.high_estimate),
            "sources_used": self.sources_used,
            "confidence_summary": self.confidence_summary,
            "methodology": self.methodology,
        }


async def estimate_cost(
    session: AsyncSession,
    code: str,
    location_zip3: str | None,
    payer: str | None = None,
    hospital_id: str | None = None,
) -> CostEstimate:
    """Confidence-banded cost estimate for a code (+ optional location/payer/hospital)."""
    q = select(TransparencyRate).where(
        TransparencyRate.code == code, TransparencyRate.source != "trilliant"
    )
    if payer:
        q = q.where(TransparencyRate.payer == payer)
    if hospital_id:
        q = q.where(TransparencyRate.hospital_id == hospital_id)
    rows = list((await session.execute(q)).scalars().all())

    # Prefer rows matching the location, but keep national-baseline rows (zip3 null).
    if location_zip3:
        loc = [r for r in rows if r.location_zip3 in (location_zip3, None)]
        rows = loc or rows

    market = [r for r in rows if r.source in _MARKET_SOURCES and r.rate is not None]
    baseline = [r for r in rows if r.source == "medicare_pfs" and r.rate is not None]

    if not baseline:
        # Always-available fallback: the national Medicare baseline for this code.
        bq = select(TransparencyRate).where(
            TransparencyRate.code == code, TransparencyRate.source == "medicare_pfs"
        )
        baseline = list((await session.execute(bq)).scalars().all())

    if market:
        return _from_market(code, location_zip3, market, baseline)
    if baseline:
        return _from_baseline(code, location_zip3, baseline)
    return CostEstimate(
        code=code,
        location_zip3=location_zip3,
        central_estimate=None,
        low_estimate=None,
        high_estimate=None,
        sources_used=[],
        confidence_summary="No pricing data available yet for this code.",
        methodology="No Medicare baseline or transparency rates ingested for this code.",
    )


def _from_market(code, location_zip3, market, baseline) -> CostEstimate:
    rates = sorted(Decimal(str(r.rate)) for r in market)
    central = _weighted_central(market)
    if len(rates) >= 2:
        q = statistics.quantiles([float(x) for x in rates], n=4)
        low, high = Decimal(str(round(q[0], 2))), Decimal(str(round(q[2], 2)))
    else:
        low = high = rates[0]
    sources = sorted({r.source for r in market} | ({"medicare_pfs"} if baseline else set()))
    n = len(market)
    conf = (
        f"High confidence — corroborated by {n} market rate(s) across {len(set(r.source for r in market))} source(s)"
        if n >= 3
        else f"Moderate confidence — {n} market rate(s); band reflects observed spread"
    )
    return CostEstimate(
        code=code,
        location_zip3=location_zip3,
        central_estimate=central,
        low_estimate=low,
        high_estimate=high,
        sources_used=sources,
        confidence_summary=conf,
        methodology=(
            "Confidence-weighted central of negotiated transparency rates (hospital MRF + "
            "TiC), with the 25th–75th percentile as the band. Good-faith estimate, not a quote."
        ),
    )


def _from_baseline(code, location_zip3, baseline) -> CostEstimate:
    central = Decimal(str(baseline[0].rate))
    low = (central * (Decimal("1") - _BASELINE_BAND)).quantize(Decimal("0.01"))
    high = (central * (Decimal("1") + _BASELINE_BAND)).quantize(Decimal("0.01"))
    return CostEstimate(
        code=code,
        location_zip3=location_zip3,
        central_estimate=central,
        low_estimate=low,
        high_estimate=high,
        sources_used=["medicare_pfs"],
        confidence_summary="Medicare baseline only — confidence band ±35%.",
        methodology=(
            "No negotiated transparency rates ingested for this code+location yet; the estimate "
            "is the Medicare allowable with a ±35% band. Good-faith estimate, not a quote."
        ),
    )


def _weighted_central(market) -> Decimal:
    total_w = sum(float(r.confidence_score or 0) for r in market)
    if total_w <= 0:
        vals = sorted(float(r.rate) for r in market)
        return Decimal(str(round(statistics.median(vals), 2)))
    weighted = sum(float(r.rate) * float(r.confidence_score) for r in market) / total_w
    return Decimal(str(round(weighted, 2)))
