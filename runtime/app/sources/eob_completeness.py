"""EOB-completeness confirmation (Sprint D, DL-86).

Before the accumulator totals are treated as COMPLETE — regardless of source (document
uploads today; 1upHealth later) — Tyndale summarizes what it has (count, plan-year span,
whether more than one person appears) and asks the user "does that look like all of them?".
Only an affirmative answer flips ``all_plan_year_eobs_confirmed`` so the cross-validation
stops calling a partial pile "corroborated".

This module is a PURE summarizer over the eobs list — source-agnostic on purpose. It reads
the same wrapped-or-flat EOB shape the accumulator adapter reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None


def _unwrap(entry) -> dict:
    """EOBs are stored either flat or wrapped as {'eob': {...}} (matches the adapter)."""
    if not isinstance(entry, dict):
        return {}
    return entry.get("eob", entry) if isinstance(entry.get("eob"), dict) else entry


def _plan_year(coverage: dict, dated: list[date]) -> int | None:
    cov = coverage or {}
    if cov.get("plan_year"):
        try:
            return int(cov["plan_year"])
        except (ValueError, TypeError):
            pass
    eff = cov.get("plan_effective_date")
    if eff:
        d = _parse_date(eff)
        if d:
            return d.year
    if dated:
        return max(dated).year
    return None


@dataclass
class EobCompletenessSummary:
    eob_count: int
    plan_year: int | None
    date_start: str | None
    date_end: str | None
    dated_count: int
    undated_count: int
    patient_names: list[str] = field(default_factory=list)
    covers_family: bool = False
    confirmed: bool | None = None  # from coverage['all_plan_year_eobs_confirmed']
    question: str = ""

    def to_dict(self) -> dict:
        return {
            "eob_count": self.eob_count,
            "plan_year": self.plan_year,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "dated_count": self.dated_count,
            "undated_count": self.undated_count,
            "patient_names": list(self.patient_names),
            "covers_family": self.covers_family,
            "confirmed": self.confirmed,
            "question": self.question,
        }


def _month_span(start: date | None, end: date | None) -> str:
    if start is None and end is None:
        return "no dated statements"
    if start and end and (start.month, start.year) != (end.month, end.year):
        if start.year == end.year:
            return f"{_MONTHS[start.month - 1]}–{_MONTHS[end.month - 1]} {end.year}"
        return f"{_MONTHS[start.month - 1]} {start.year}–{_MONTHS[end.month - 1]} {end.year}"
    d = start or end
    return f"{_MONTHS[d.month - 1]} {d.year}"


def summarize_eob_completeness(
    eobs: list | None, coverage: dict | None
) -> EobCompletenessSummary:
    """Build the plain-language completeness summary + confirmation question."""
    eobs = eobs or []
    coverage = coverage or {}
    dated: list[date] = []
    undated = 0
    names: list[str] = []
    for entry in eobs:
        eob = _unwrap(entry)
        d = _parse_date(eob.get("adjudication_date")) or _parse_date(eob.get("date_of_service"))
        if d:
            dated.append(d)
        else:
            undated += 1
        name = (eob.get("patient_name") or eob.get("member_name") or "").strip()
        if name and name not in names:
            names.append(name)

    start = min(dated) if dated else None
    end = max(dated) if dated else None
    covers_family = len(names) > 1

    count = len(eobs)
    span = _month_span(start, end)
    family_clause = (
        f", covering {len(names)} people" if covers_family
        else ", none for family members" if names
        else ""
    )
    plural = "s" if count != 1 else ""
    question = (
        f"{count} EOB{plural} this plan year, {span}{family_clause} — does that look like "
        "all of them?"
    )

    return EobCompletenessSummary(
        eob_count=count,
        plan_year=_plan_year(coverage, dated),
        date_start=start.isoformat() if start else None,
        date_end=end.isoformat() if end else None,
        dated_count=len(dated),
        undated_count=undated,
        patient_names=names,
        covers_family=covers_family,
        confirmed=(
            bool(coverage["all_plan_year_eobs_confirmed"])
            if "all_plan_year_eobs_confirmed" in coverage
            else None
        ),
        question=question,
    )
