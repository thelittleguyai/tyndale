"""Tyndale Record data helpers (D5, Phase C — DL-91). The data-honesty rules (§4) are encoded here
so both /v1/record and the sub-case summary share one honest source of truth:

- recovered/avoided totals come ONLY from CONFIRMED outcome_report events (resolved yes|partial),
  de-duped to the latest report per case — NEVER from a finding's estimated savings.
- the finding estimate (facts['gap']) is 'identified' potential savings — surfaced separately and
  labeled, never summed into recovered.
- deadline clocks come only from persisted deadline rows; the provenance source is joined from the
  appeals rule table (shadow-mode data is fine to DISPLAY as informational).
- a sub-case with no computed three-number carries None here — the view shows needs-documents, not
  {0,0,0} (the CO-15 rule extends to the Record).
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appeals.deadlines import DEADLINE_RULES
from app.config import get_settings
from app.db.models.deadlines import Deadline
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.schemas.case_file import as_dict

_RECOVERED_STATES = ("yes", "partial")  # only genuine recoveries count toward the total


def _outcome_amount(payload: dict) -> float | None:
    o = (payload or {}).get("outcome") or {}
    if o.get("resolved") in _RECOVERED_STATES and o.get("amount_saved") is not None:
        try:
            return float(o["amount_saved"])
        except (TypeError, ValueError):
            return None
    return None


async def confirmed_recovered_by_case(
    session: AsyncSession, case_ids: list
) -> dict[str, float]:
    """Confirmed recovered $ per case — the LATEST outcome_report only (a re-report can't inflate).
    Cases with no confirmed recovery are absent (caller defaults to 0.0 / 'so far')."""
    if not case_ids:
        return {}
    rows = (
        await session.execute(
            select(FeedbackEvent.case_file_id, FeedbackEvent.payload, FeedbackEvent.created_at)
            .where(FeedbackEvent.case_file_id.in_(case_ids))
            .where(FeedbackEvent.feedback_type == "outcome_report")
            .order_by(FeedbackEvent.created_at.desc())
        )
    ).all()
    out: dict[str, float] = {}
    for cid, payload, _created in rows:
        key = str(cid)
        if key in out:  # already have the latest (rows are desc)
            continue
        amt = _outcome_amount(payload or {})
        if amt is not None:
            out[key] = amt
    return out


def three_number_from_findings(findings: list[Finding]) -> dict | None:
    """The three numbers from the first finding whose facts carry all three (never {0,0,0})."""
    for f in findings:
        facts = as_dict(f.facts) or {}
        pb, eob, tc = (
            facts.get("provider_billed"),
            facts.get("eob_member_responsibility"),
            facts.get("tyndale_computed"),
        )
        if pb is not None and eob is not None and tc is not None:
            try:
                return {
                    "provider_billed": float(pb),
                    "eob_member_responsibility": float(eob),
                    "tyndale_computed": float(tc),
                }
            except (TypeError, ValueError):
                continue
    return None


def identified_estimate_from_findings(findings: list[Finding]) -> float:
    """Potential savings IDENTIFIED by the audit (finding estimate, facts['gap']) — an ESTIMATE,
    shown separately and labeled, NEVER folded into recovered. Sums the positive gap of EVERY
    finding, payer-side and provider-side alike: the Independent Audit Doctrine pursues both with
    equal rigor, and the sub-case summary's gameplan lists provider-side steps with their own
    dollar figures, so a payer-only total would under-count and contradict its own gameplan."""
    total = 0.0
    for f in findings:
        gap = (as_dict(f.facts) or {}).get("gap")
        if gap is not None:
            try:
                total += max(0.0, float(gap))
            except (TypeError, ValueError):
                pass
    return round(total, 2)


def open_item_count(findings: list[Finding]) -> int:
    return sum(1 for f in findings if (getattr(f, "status", None) or "open") == "open")


def next_check_in_date(case, findings: list[Finding]) -> datetime.date | None:
    """The nudge scheduler's next planned touch: anchor (earliest finding) + the first un-sent
    stage. None when there's no recommendation yet or both stages are exhausted."""
    times = [f.created_at for f in findings if f.created_at is not None]
    if not times:
        return None
    settings = get_settings()
    anchor = min(times)
    stages = [("+3d", settings.nudge_first_days), ("+14d", settings.nudge_second_days)]
    sent = set(case.nudges_sent or [])
    nxt = next((days for label, days in stages if label not in sent), None)
    if nxt is None:
        return None
    return (anchor + datetime.timedelta(days=nxt)).date()


async def deadlines_for_case(session: AsyncSession, case_file_id) -> list[dict]:
    """Informational dispute/appeal clocks from PERSISTED rows only (no clock invented from copy).
    The provenance `source` is joined from the appeals rule table by deadline_type."""
    rows = (
        await session.execute(
            select(Deadline)
            .where(Deadline.case_file_id == case_file_id)
            .where(Deadline.status == "pending")
            .order_by(Deadline.deadline_date)
        )
    ).scalars().all()
    out: list[dict] = []
    for d in rows:
        rule = DEADLINE_RULES.get(d.deadline_type)
        out.append({
            "label": rule.label if rule else (d.description or d.deadline_type),
            "due_date": d.deadline_date.isoformat() if d.deadline_date else None,
            "source": rule.source if rule else d.deadline_type,
        })
    return out
