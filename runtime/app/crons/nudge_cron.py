"""Nudge scheduler for open load-bearing data-fetch items (Sprint G).

When an audit is gated on a document the user must fetch (Sprint C's USER_CHASE / tier-3
chase items), nudge at +3 days and +14 days, then stop sending — after that it's in-app
resurfacing only (the dashboard already surfaces the chase card). ONE bundled message per
case per send; idempotent via the case's ``nudges_sent`` ledger so a stage never double-fires.

Email only for now (SendGrid; the SMS seam is left for the Twilio decision). Every send goes
through the PHI email guard — nudge copy names DOCUMENT TYPES, never amounts or providers
(DL-47).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding
from app.db.models.users import User
from app.sources.materiality import USER_CHASE, is_material
from app.sources.missing_data_priors import MISSING_DATA_PRIORS, missing_cost_share_inputs

log = structlog.get_logger(__name__)

# Chase input → the PHI-free document type that resolves it (never names amounts/providers).
_CHASE_DOC_LABELS: dict[str, str] = {
    "deductible_amount": "your plan's Summary of Benefits (SBC)",
    "oop_max_amount": "your plan's Summary of Benefits (SBC)",
    "coinsurance_percent": "your plan's Summary of Benefits (SBC)",
}

# Statuses whose cases are still "open" for a data-fetch nudge.
_OPEN_STATUSES = ("audit_complete", "audit_incomplete", "awaiting_eob_confirmation")

# Sender signature: (to_email, subject, body) -> awaitable. Injectable for tests.
NudgeSender = Callable[[str, str, str], Awaitable[bool]]


@dataclass
class NudgeItem:
    user_id: str
    case_file_id: str
    stage: str  # "+3d" | "+14d"
    documents: list[str] = field(default_factory=list)
    email: str | None = None
    days_since: int = 0

    def subject(self) -> str:
        return "One document would finish your Tyndale case"

    def body(self) -> str:
        docs = " and ".join(self.documents) if self.documents else "a plan document"
        # PHI-free by construction: only document types, no amounts/providers/names.
        return (
            f"Hi — your Tyndale case is almost done. To lock in the numbers, we still need "
            f"{docs}. You can add it in the app whenever it's handy, and Tyndale will finish "
            f"the review automatically. No rush — this is just a reminder."
        )


def _chase_documents(coverage: dict | None) -> list[str]:
    """The distinct PHI-free document labels for the case's USER_CHASE-level missing inputs."""
    chase = [
        k
        for k in missing_cost_share_inputs(coverage)
        if (p := MISSING_DATA_PRIORS.get(k)) and is_material(p.usd_span(), p.high, USER_CHASE)
    ]
    seen: list[str] = []
    for k in chase:
        label = _CHASE_DOC_LABELS.get(k)
        if label and label not in seen:
            seen.append(label)
    return seen


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _due_stage(days_since: int, already_sent: list[str], first: int, second: int) -> str | None:
    """The single stage a case is due for, else None. Once the second nudge is sent, no more
    sends (contextual in-app resurfacing takes over) — and a case old enough for +14d gets
    that, never a late +3d."""
    if "+14d" in already_sent:
        return None
    if days_since >= second:
        return "+14d"
    if days_since >= first and "+3d" not in already_sent:
        return "+3d"
    return None


async def scan_for_nudges(now: datetime | None = None) -> list[NudgeItem]:
    """Cases due for a data-fetch nudge: an open case with a USER_CHASE-level missing
    document, whose recommendation is old enough for the next unsent stage. One item per
    case (bundled)."""
    settings = get_settings()
    first, second = settings.nudge_first_days, settings.nudge_second_days
    now = _aware(now or datetime.now(timezone.utc))
    out: list[NudgeItem] = []

    async with AsyncSessionLocal() as s:
        cases = (
            await s.execute(select(CaseFile).where(CaseFile.status.in_(_OPEN_STATUSES)))
        ).scalars().all()
        for case in cases:
            documents = _chase_documents(case.coverage)
            if not documents:
                continue  # nothing load-bearing to chase (or already provided)

            findings = (
                await s.execute(select(Finding.created_at).where(Finding.case_file_id == case.case_file_id))
            ).scalars().all()
            times = [_aware(t) for t in findings if t is not None]
            if not times:
                continue  # no audit recommendation yet → nothing to nudge about
            days_since = (now - min(times)).days

            stage = _due_stage(days_since, list(case.nudges_sent or []), first, second)
            if stage is None:
                continue

            user = (
                await s.execute(select(User).where(User.user_id == case.user_id))
            ).scalar_one_or_none()
            out.append(
                NudgeItem(
                    user_id=str(case.user_id),
                    case_file_id=str(case.case_file_id),
                    stage=stage,
                    documents=documents,
                    email=user.email if user else None,
                    days_since=days_since,
                )
            )
    return out


async def _mark_sent(case_file_id: str, stage: str) -> None:
    from uuid import UUID

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        if case is None:
            return
        sent = list(case.nudges_sent or [])
        if stage not in sent:
            sent.append(stage)
            case.nudges_sent = sent
            await s.commit()


async def _guarded_email_sender(to_email: str, subject: str, body: str) -> bool:
    """Actually send the nudge (DL-47 PHI guard runs inside `send_product_email`).

    Until 2026-08-12 this ran the guard, logged "sent", and returned True **without calling
    SendGrid** — so `_mark_sent` stamped the case's ledger and, because the ledger blocks a
    retry, that stage's email was lost for good. Returning the real send result is what makes
    the ledger mean what it says. TODO(phil-decision): SMS via Twilio (seam left).
    """
    from app.notify.email import send_product_email

    return await send_product_email(to_email, subject, body, kind="nudge")


async def run_nudge_cron(sender: NudgeSender | None = None) -> dict:
    """Scan + (when enabled) send one bundled nudge per due case, marking each stage so it
    never double-sends. Sends are gated behind ENABLE_NUDGE_EMAILS — the scan always runs."""
    settings = get_settings()
    send = sender or _guarded_email_sender
    items = await scan_for_nudges()
    sent = 0
    skipped = 0
    for item in items:
        if not settings.enable_nudge_emails or not item.email:
            skipped += 1
            continue
        ok = await send(item.email, item.subject(), item.body())
        if ok:
            await _mark_sent(item.case_file_id, item.stage)
            sent += 1
            # Internal analytics (P0): nudge_sent, keyed to the funnel stage. Best-effort.
            from app.analytics.emit import emit

            await emit(
                "nudge_sent", user_id=uuid.UUID(item.user_id),
                case_file_id=uuid.UUID(item.case_file_id),
                properties={"stage": "first" if item.stage == "+3d" else "second"},
            )
        else:
            skipped += 1
    return {"due": len(items), "sent": sent, "skipped": skipped}
