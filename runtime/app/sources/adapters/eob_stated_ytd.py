"""EOBStatedYTD — the corroborating AccumulatorSource reading (CO-12B).

Reads the year-to-date deductible / OOP figures the EOBs STATE directly. This is the
payer's CLAIM about the accumulator — surfaced for three-way cross-validation in
BenefitsContext, audited, never adopted as the answer (Independent Audit Doctrine).
The authoritative figure is ComputedFromUploadedEOBs; this is only a comparison.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.schemas.provenance import Provenance
from app.sources.base import AccumulatorResult
from app.sources.case_data import as_float, load_case_eobs_coverage, parse_iso_date


def read_eob_stated_ytd(eobs: list[dict], as_of: date) -> dict[str, Any]:
    """Pure: the latest stated YTD deductible/OOP across this plan year's EOBs.

    YTD figures are cumulative, so the most recent EOB's stated value is current;
    undated values lose to dated ones. Missing -> None (never synthesized)."""
    plan_year = as_of.year
    latest_ded: tuple[date, float] | None = None
    latest_oop: tuple[date, float] | None = None
    for entry in eobs:
        eob = entry.get("eob", entry) if isinstance(entry, dict) else {}
        dt = parse_iso_date(eob.get("adjudication_date")) or parse_iso_date(
            eob.get("date_of_service")
        )
        if dt is not None and dt.year != plan_year:
            continue
        key = dt or date.min  # undated sorts earliest, so a dated reading wins
        d = as_float(eob.get("deductible_ytd_stated"))
        o = as_float(eob.get("oop_ytd_stated"))
        if d is not None and (latest_ded is None or key >= latest_ded[0]):
            latest_ded = (key, d)
        if o is not None and (latest_oop is None or key >= latest_oop[0]):
            latest_oop = (key, o)
    return {
        "deductible_applied": latest_ded[1] if latest_ded else None,
        "oop_applied": latest_oop[1] if latest_oop else None,
    }


class EOBStatedYTD:
    """AccumulatorSource — the EOB's own stated YTD figures (audited, not adopted)."""

    adapter_name = "EOBStatedYTD"

    async def get_accumulator(
        self, case_file_id: str, as_of: date, args: dict[str, Any] | None = None
    ) -> AccumulatorResult:
        eobs, _ = await load_case_eobs_coverage(case_file_id)
        data = read_eob_stated_ytd(eobs, as_of)
        stated = data["deductible_applied"] is not None or data["oop_applied"] is not None
        return AccumulatorResult(
            data=data,
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="user_upload",
                as_of=datetime(as_of.year, as_of.month, as_of.day),
                confidence=0.5 if stated else 0.0,
                assumptions=[
                    "year-to-date figures as STATED by the payer's EOB — audited, not adopted"
                ],
            ),
        )
