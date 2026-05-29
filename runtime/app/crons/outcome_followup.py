"""Outcome follow-up scanning (Phase 2J).

scan_for_outcome_followups() finds case files where Tyndale gave the user a
scripted action and enough time has passed without an outcome being reported —
those become the dashboard's "how did it go?" prompts.

V1-Lite: called synchronously by GET /v1/feedback/outcome-prompts (and inlined
into the dashboard payload). Phase 4 adds a scheduled job that calls the same
function and fires notify_user pushes/email.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding

log = structlog.get_logger(__name__)


@dataclass
class OutcomeFollowup:
    user_id: str
    case_file_id: str
    days_since_recommendation: int
    finding_summary: str


def _humanize(category: str) -> str:
    return category.replace("_", " ").strip().capitalize()


def _summary_for(findings: list[Finding]) -> str:
    """Build a short human summary from the recommendation finding(s)."""
    rec = next((f for f in findings if (f.recommendation or {}).get("action")), None)
    if rec is None:
        return "your case"
    label = _humanize(rec.category)
    # Try to name the payer from the finding facts if present.
    payer = (rec.facts or {}).get("payer_name") or (rec.facts or {}).get("payer")
    return f"{label} with {payer}" if payer else label


async def scan_for_outcome_followups(user_id: str | None = None) -> list[OutcomeFollowup]:
    """Return cases eligible for an outcome prompt.

    Eligible when ALL of:
      - status == 'audit_complete'
      - has >= 1 finding with a scripted recommendation (recommendation.action),
        OR a Tier C finding
      - last_outcome_check_at IS NULL OR older than the threshold
      - no outcome_report feedback event exists yet
      - the recommendation was given >= outcome_followup_days ago (we use the
        earliest recommendation finding's created_at as the recommendation time)
    """
    settings = get_settings()
    threshold_days = getattr(settings, "outcome_followup_days", 14)
    now = datetime.now(timezone.utc)
    out: list[OutcomeFollowup] = []

    async with AsyncSessionLocal() as s:
        q = select(CaseFile).where(CaseFile.status == "audit_complete")
        if user_id:
            from uuid import UUID

            q = q.where(CaseFile.user_id == UUID(user_id))
        cases = (await s.execute(q)).scalars().all()

        for case in cases:
            # Already answered/skipped recently?
            if case.last_outcome_check_at is not None:
                age = (now - _aware(case.last_outcome_check_at)).days
                if age < threshold_days:
                    continue

            findings = (await s.execute(
                select(Finding).where(Finding.case_file_id == case.case_file_id)
            )).scalars().all()
            rec_findings = [
                f for f in findings
                if (f.recommendation or {}).get("action") or f.voice_tier == "C"
            ]
            if not rec_findings:
                continue

            # Already reported an outcome?
            outcome_exists = (await s.execute(
                select(FeedbackEvent)
                .where(FeedbackEvent.case_file_id == case.case_file_id)
                .where(FeedbackEvent.feedback_type == "outcome_report")
                .limit(1)
            )).first()
            if outcome_exists is not None:
                continue

            rec_time = min(_aware(f.created_at) for f in rec_findings if f.created_at)
            days = (now - rec_time).days
            if days < threshold_days:
                continue

            out.append(
                OutcomeFollowup(
                    user_id=str(case.user_id),
                    case_file_id=str(case.case_file_id),
                    days_since_recommendation=days,
                    finding_summary=_summary_for(rec_findings),
                )
            )
    return out


def _aware(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to UTC-aware for subtraction."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
