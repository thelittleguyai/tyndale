"""ComputedFromUploadedEOBs — the deterministic AccumulatorSource engine (CO-12B).

Reconstructs how much of the deductible / out-of-pocket max has been met THIS plan
year by summing the applied-amounts across the uploaded EOBs — independently of what
any EOB claims the member owes (Independent Audit Doctrine). The math is a PURE
DETERMINISTIC FUNCTION (``compute_accumulator``), never a model/LLM computation; the
adapter only loads CaseFile data and calls it.

Graceful degradation (never a dead-end): undated EOBs are included + flagged; missing
family/embedded structure falls back to a single individual/in-network bucket with a
recorded assumption; an unconfirmed completeness gate lowers confidence + records it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.schemas.provenance import Provenance
from app.sources.base import AccumulatorResult
from app.sources.case_data import as_float, load_case_eobs_coverage, parse_iso_date


@dataclass
class AccumulatorComputation:
    """Pure result of the reconstruction: payload + recorded assumptions + confidence."""

    data: dict[str, Any]
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0


def _accumulator_confidence(
    *,
    total: int,
    dated: int,
    with_applied: int,
    all_eobs_uploaded: bool | None,
    bucketing_assumed: bool,
) -> float:
    """Deterministic confidence in [0, 1].

    Base 0.70 for a reconstruction from uploaded EOBs, scaled by how usable the set
    is — the mean of (fraction with a usable date) and (fraction contributing an
    applied amount), since ordering/plan-year needs dates and the sum needs amounts.
    Then x0.60 when completeness is unconfirmed (the biggest unknown), and x0.85 when
    a bucketing assumption was required (plan structure not captured). Empty set -> 0.0.
    """
    if total == 0:
        return 0.0
    usable = 0.5 * (dated / total) + 0.5 * (with_applied / total)
    conf = 0.70 * usable
    if all_eobs_uploaded is not True:
        conf *= 0.60
    if bucketing_assumed:
        conf *= 0.85
    return round(max(0.0, min(1.0, conf)), 3)


def compute_accumulator(
    eobs: list[dict],
    coverage: dict | None,
    as_of: date,
    all_eobs_uploaded: bool | None,
) -> AccumulatorComputation:
    """Pure deductible/OOP reconstruction from the uploaded EOB set. No I/O, no LLM."""
    coverage = coverage or {}
    # V1-Lite: plan year == calendar year of as_of (plan-start month not captured yet).
    plan_year = as_of.year
    assumptions: list[str] = []

    # 1-2. Date each EOB (adjudication_date; date_of_service fallback, flagged), keep
    #       this plan year (undated included + flagged), order by date (undated last).
    used_dos_fallback = False
    undated = 0
    rows: list[tuple[date | None, dict]] = []
    for entry in eobs:
        eob = entry.get("eob", entry) if isinstance(entry, dict) else {}
        dt = parse_iso_date(eob.get("adjudication_date"))
        if dt is None:
            dos = parse_iso_date(eob.get("date_of_service"))
            if dos is not None:
                dt, used_dos_fallback = dos, True
        if dt is None:
            undated += 1
        if dt is None or dt.year == plan_year:
            rows.append((dt, eob))
    rows.sort(key=lambda r: (r[0] is None, r[0] or date.min))
    if used_dos_fallback:
        assumptions.append(
            "some EOBs lacked an adjudication date; date_of_service used as fallback "
            "for ordering/plan-year"
        )
    if undated:
        assumptions.append(f"{undated} undated EOB(s) included — could not confirm plan year")

    # 3. Bucket. V1-Lite coverage carries no family/embedded structure -> a single
    #    individual in-network bucket (recorded assumption — the degradation rung).
    has_structure = any(
        k in coverage for k in ("family_deductible_amount", "deductible_individual", "embedded")
    )
    if not has_structure:
        assumptions.append(
            "family/embedded deductible structure not captured in coverage; assumed "
            "individual in-network single bucket"
        )

    ded_applied = 0.0
    oop_applied = 0.0
    dated_count = 0
    with_applied = 0
    for dt, eob in rows:
        if dt is not None:
            dated_count += 1
        d = as_float(eob.get("amount_applied_to_deductible"))
        o = as_float(eob.get("amount_applied_to_oop"))
        if d is not None:
            ded_applied += d
        if o is not None:
            oop_applied += o
        if d is not None or o is not None:
            with_applied += 1
    ded_applied = round(ded_applied, 2)
    oop_applied = round(oop_applied, 2)

    # 4. Remaining (only when coverage exposes the cap).
    ded_cap = as_float(coverage.get("deductible_amount"))
    oop_cap = as_float(coverage.get("oop_max_amount"))
    ded_remaining = round(max(ded_cap - ded_applied, 0.0), 2) if ded_cap is not None else None
    oop_remaining = round(max(oop_cap - oop_applied, 0.0), 2) if oop_cap is not None else None

    # Completeness gate (graceful degradation, never a dead-end).
    if all_eobs_uploaded is not True:
        assumptions.append(
            "EOB history may be incomplete — user has not confirmed all plan-year EOBs uploaded"
        )

    confidence = _accumulator_confidence(
        total=len(rows),
        dated=dated_count,
        with_applied=with_applied,
        all_eobs_uploaded=all_eobs_uploaded,
        bucketing_assumed=not has_structure,
    )
    data = {
        "deductible_applied": ded_applied,
        "oop_applied": oop_applied,
        "deductible_remaining": ded_remaining,
        "oop_remaining": oop_remaining,
        "eobs_counted": len(rows),
        "plan_year": plan_year,
        "buckets": {
            "individual_in_network": {
                "deductible_applied": ded_applied,
                "oop_applied": oop_applied,
            }
        },
    }
    return AccumulatorComputation(data=data, assumptions=assumptions, confidence=confidence)


def completeness_signal(args: dict[str, Any] | None, coverage: dict | None) -> bool | None:
    """The 'all of this plan year's EOBs uploaded' gate. Read from the call args, or
    the flag CO-12C's guided confirmation persists on the case
    (coverage['all_plan_year_eobs_confirmed']). Unknown -> None (treated as
    unconfirmed -> lower confidence + recorded assumption)."""
    if args and "all_eobs_uploaded" in args:
        return bool(args["all_eobs_uploaded"])
    coverage = coverage or {}
    # CO-12C guided flow sets this key via the intake "all plan-year EOBs?" question.
    if "all_plan_year_eobs_confirmed" in coverage:
        return bool(coverage["all_plan_year_eobs_confirmed"])
    if "_all_eobs_uploaded" in coverage:  # back-compat (CO-12B interim key)
        return bool(coverage["_all_eobs_uploaded"])
    return None


class ComputedFromUploadedEOBs:
    """AccumulatorSource — deterministic reconstruction from CaseFile.eobs."""

    adapter_name = "ComputedFromUploadedEOBs"

    async def get_accumulator(
        self, case_file_id: str, as_of: date, args: dict[str, Any] | None = None
    ) -> AccumulatorResult:
        eobs, coverage = await load_case_eobs_coverage(case_file_id)
        comp = compute_accumulator(eobs, coverage, as_of, completeness_signal(args, coverage))
        return AccumulatorResult(
            data=comp.data,
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="computed",
                as_of=datetime(as_of.year, as_of.month, as_of.day),
                confidence=comp.confidence,
                assumptions=comp.assumptions,
            ),
        )
