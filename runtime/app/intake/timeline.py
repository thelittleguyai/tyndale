"""The EOB timeline (doc 40 §A7) — Phase 1 subset: upload-fed, the single patient row.

Anchors on the plan-year START — read from the SBC's own "Coverage Period" line when there is
one, else the user's answer to the plan-year ask. **Never assumed to be January 1.** The date of
service of the bill being checked is marked on it; every month between the plan-year start and
that date which has no EOB is a named gap; EOBs dated AFTER the visit are collected and shown,
and visibly marked as not affecting this bill's position.

The model is ready for what Phase 2 renders: every row carries ``member`` (the covered person —
a family plan's deductible accumulates across everyone) and ``network`` (in | out | None — the
two accumulate separately), and a ``source`` from the typed ``TimelineSource`` seam so EOBs that
arrive from a coverage connection land without a schema change. The timeline is UPLOAD-FED:
email forwarding was dropped (Brock 2026-09-21, decision 6 — an injection surface that needs its
own security design first); there is no forwarding source, seam or copy.
"""

from __future__ import annotations

import datetime
import re
from typing import Literal

from app.sources.eob_completeness import _parse_date, _unwrap

# Typed seam (§A7): only `upload` is offered. `api` (a coverage connection) exists so its arrival
# is a new value, not a migration — and so nothing renders a button for it until it is real.
# Email forwarding is DROPPED (decision 6), not merely unoffered: no value is kept for it.
TimelineSource = Literal["upload", "api"]
TIMELINE_SOURCES: tuple[str, ...] = ("upload", "api")
OFFERED_SOURCES: tuple[str, ...] = ("upload",)

EOB_DOC_TYPES = frozenset({"eob", "ma_eob", "msn", "tricare_eob"})
SBC_DOC_TYPES = frozenset({"sbc", "plan_summary"})

_PERIOD = re.compile(
    r"coverage\s+period\s*:?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s*(?:-|–|—|to|through)\s*"
    r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
    re.I,
)
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip


def _year(y: str) -> int:
    n = int(y)
    return n + 2000 if n < 100 else n


def coverage_period_from_text(text: str | None) -> tuple[str, str] | None:
    """('2025-01-01', '2025-12-31') from an SBC's "Coverage Period: 01/01/2025 – 12/31/2025"
    — the line CMS's template prints top-right of page 1. None when it is not there."""
    m = _PERIOD.search(text or "")
    if not m:
        return None
    try:
        start = datetime.date(_year(m.group(3)), int(m.group(1)), int(m.group(2)))
        end = datetime.date(_year(m.group(6)), int(m.group(4)), int(m.group(5)))
    except ValueError:
        return None
    return (start.isoformat(), end.isoformat()) if start < end else None


def plan_year_start_from_documents(documents: list | None) -> str | None:
    for d in documents or []:
        if isinstance(d, dict) and d.get("document_type") in SBC_DOC_TYPES:
            period = coverage_period_from_text(d.get("ocr_text"))
            if period:
                return period[0]
    return None


def resolved_plan_year_start(case) -> tuple[str | None, str | None]:
    """(start, source): the SBC's own "Coverage Period" first, then the user's answer to the
    plan-year ask. Never assumed to be January 1 — unknown is (None, None)."""
    sbc = plan_year_start_from_documents(getattr(case, "documents", None))
    if sbc:
        return sbc, "sbc"
    user = (getattr(case, "coverage", None) or {}).get("plan_effective_date")
    return (str(user), "user") if user else (None, None)


def persist_plan_year_start(case) -> bool:
    """Write the resolved plan-year start onto the case's COVERAGE record
    (coverage.plan_year_start + plan_year_start_source). The retention schedule (doc 43, Brock
    2026-09-21 decision 9) keeps a plan year's EOBs through the end of THAT plan year — it must
    read the anchor after the intake snapshot is gone. True when the record changed; the caller
    commits."""
    start, source = resolved_plan_year_start(case)
    cov = dict(getattr(case, "coverage", None) or {})
    if not start or (cov.get("plan_year_start"), cov.get("plan_year_start_source")) == (start, source):
        return False
    cov["plan_year_start"], cov["plan_year_start_source"] = start, source
    case.coverage = cov
    return True


def plan_year_start_for(month: int, date_of_service: datetime.date | None) -> str:
    """The user names the MONTH their plan year starts; the year follows from the visit: the
    latest such month-start on or before the date of service (today, when it is unknown)."""
    anchor = date_of_service or datetime.date.today()
    year = anchor.year if (anchor.month, anchor.day) >= (month, 1) else anchor.year - 1
    return datetime.date(year, month, 1).isoformat()


def eob_rows(case) -> list[dict]:
    """One row per EOB the case holds — structured ``case.eobs`` entries and EOB-typed
    documents (deduped by document id). Undated rows are kept and say so."""
    rows: list[dict] = []
    seen: set[str] = set()
    for entry in getattr(case, "eobs", None) or []:
        eob = _unwrap(entry)
        if not eob:
            continue
        doc_id = str(eob.get("document_id") or "")
        if doc_id:
            seen.add(doc_id)
        d = _parse_date(eob.get("date_of_service")) or _parse_date(eob.get("adjudication_date"))
        rows.append(
            {
                "document_id": doc_id or None,
                "date": d.isoformat() if d else None,
                "member": (eob.get("member") or eob.get("patient_name") or eob.get("member_name") or None),
                "network": eob.get("network") if eob.get("network") in ("in", "out") else None,
                "claim_number": eob.get("claim_number"),
                "source": eob.get("source") if eob.get("source") in TIMELINE_SOURCES else "upload",
            }
        )
    for d in getattr(case, "documents", None) or []:
        if not isinstance(d, dict) or d.get("document_type") not in EOB_DOC_TYPES:
            continue
        doc_id = str(d.get("document_id") or "")
        if doc_id and doc_id in seen:
            continue
        when = _parse_date(d.get("date_of_service"))
        rows.append(
            {
                "document_id": doc_id or None,
                "date": when.isoformat() if when else None,
                "member": d.get("member") or d.get("patient_name") or None,
                "network": d.get("network") if d.get("network") in ("in", "out") else None,
                "claim_number": d.get("claim_number"),
                "source": d.get("source") if d.get("source") in TIMELINE_SOURCES else "upload",
            }
        )
    rows.sort(key=lambda r: (r["date"] is None, r["date"] or ""))
    return rows


def _months_between(start: datetime.date, end: datetime.date) -> list[tuple[int, int]]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_timeline(
    case, *, plan_year_start: str | None, date_of_service: datetime.date | None
) -> dict:
    """The timeline payload. ``gaps`` needs BOTH anchors — without a plan-year start there is
    no honest "missing February", so none is claimed."""
    rows = eob_rows(case)
    dos = date_of_service
    for r in rows:
        when = _parse_date(r["date"])
        # collected and shown — and visibly NOT part of this bill's position
        r["after_visit"] = bool(dos and when and when > dos)
        r["month_label"] = f"{_MONTHS[when.month - 1]} {when.year}" if when else None

    start = _parse_date(plan_year_start)
    gaps: list[dict] = []
    months: list[dict] = []
    if start and dos and start <= dos:
        have = {
            (w.year, w.month)
            for r in rows
            if (w := _parse_date(r["date"])) and not r["after_visit"]
        }
        for y, m in _months_between(start, dos):
            covered = (y, m) in have
            months.append({"year": y, "month": m, "label": f"{_MONTHS[m - 1]} {y}", "has_eob": covered,
                           "is_visit_month": (y, m) == (dos.year, dos.month)})
            if not covered:
                gaps.append({"year": y, "month": m, "label": MONTH_NAMES[m - 1]})
    members = sorted({r["member"] for r in rows if r["member"]})
    counted = [r for r in rows if not r["after_visit"]]
    dated = [_parse_date(r["date"]) for r in counted if r["date"]]
    return {
        "plan_year_start": start.isoformat() if start else None,
        "date_of_service": dos.isoformat() if dos else None,
        "rows": rows,
        "months": months,
        "gaps": gaps,
        "count": len(counted),
        "count_after_visit": len(rows) - len(counted),
        "undated": sum(1 for r in rows if not r["date"]),
        "span_start": MONTH_NAMES[min(dated).month - 1] if dated else None,
        "span_end": MONTH_NAMES[max(dated).month - 1] if dated else None,
        # Phase 1 renders ONE row (the patient). The model already knows who else appears.
        "members": members,
        "covers_family": len(members) > 1,
        "sources_offered": list(OFFERED_SOURCES),
    }
