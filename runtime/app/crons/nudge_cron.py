"""Nudge scheduler — the +3d/+14d cadence (Sprint G + Brock §11.5), two DIFFERENT nudges.

They were one conflated cron until 2026-08-17; reading Brock's authored copy exposed the
split, and each half now says the thing its trigger means:

**Chase** (Sprint G): the audit is gated on a document the user must fetch (USER_CHASE /
tier-3 items). The body names the missing DOCUMENT TYPE — that is the entire point of the
send — and stays engineering-written email chrome (like the magic-link and audit-ready
bodies; listed for Brock in the asks §3.7). Rendering his §11.5 check-in copy here would
tell someone we need their SBC "you're ready to make that first call," which is worse than
engineering prose.

**Check-in** (his §11.5, "contextual nudge cadence — locked"): the audit is done, a gameplan
exists, and the user hasn't acted yet. The body IS his authored `nudge.plus_3d` /
`nudge.plus_14d`, rendered from the registry so the drift guard covers it. +14d references
`{deadline_date}`; when the case has no persisted deadline the +3d string renders instead —
his own §0 rule 2 applied to email, where the in-thread degradation variant would be
nonsense in an inbox. Suppressed once the user has told us how a call went
(`last_outcome_check_at`, which the call-mode tap stamps) — "ready to make that first call?"
after they reported one is tone-deaf.

A case eligible for both gets the CHASE only (the blocked audit is the sharper fact, and one
email per case per run is the rule). Cadence for both: +3 days and +14 days, then in-app
resurfacing only. Idempotent via the case's ``nudges_sent`` ledger (chase stages "+3d"/
"+14d" keep their historical names so no case double-fires after this split; check-in stages
are "checkin+3d"/"checkin+14d"). Email only (SMS seam left for the Twilio decision); every
send passes the DL-47 PHI guard inside `send_product_email`.
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
    stage: str  # chase: "+3d" | "+14d" · check-in: "checkin+3d" | "checkin+14d"
    kind: str = "chase"  # "chase" | "checkin"
    documents: list[str] = field(default_factory=list)
    email: str | None = None
    days_since: int = 0
    deadline_date: str | None = None  # check-in +14d only, when a persisted deadline exists

    def subject(self) -> str:
        if self.kind == "checkin":
            return "Checking in on your Tyndale case"
        return "One document would finish your Tyndale case"

    def body(self) -> str:
        if self.kind == "checkin":
            return _checkin_body(self.stage, self.deadline_date)
        docs = " and ".join(self.documents) if self.documents else "a plan document"
        # PHI-free by construction: only document types, no amounts/providers/names.
        return (
            f"Hi — your Tyndale case is almost done. To lock in the numbers, we still need "
            f"{docs}. You can add it in the app whenever it's handy, and Tyndale will finish "
            f"the review automatically. No rush — this is just a reminder."
        )


def _checkin_body(stage: str, deadline_date: str | None) -> str:
    """Brock's §11.5, from the registry — his voice reaches the inbox, drift-guarded.

    +14d requires `{deadline_date}`. Without one the +3d string renders instead: his §0
    rule 2 says an unfillable variable degrades to what can be said honestly, and for email
    the honest nearest rung is the check-in line that needs no variable — never the
    in-thread degradation apology, which would be nonsense in an inbox.
    """
    from app.agents.context_loader import orchestration_step

    if stage == "checkin+14d" and deadline_date:
        return orchestration_step("nudge.plus_14d", deadline_date=deadline_date)
    return orchestration_step("nudge.plus_3d")


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


def _due_stage(
    days_since: int, already_sent: list[str], first: int, second: int, prefix: str = ""
) -> str | None:
    """The single stage a case is due for, else None. Once the second nudge is sent, no more
    sends (contextual in-app resurfacing takes over) — and a case old enough for +14d gets
    that, never a late +3d. `prefix` distinguishes the check-in ledger keys ("checkin+3d")
    from the chase's historical bare names ("+3d"), so the split can't double-fire a case
    that was already nudged before it."""
    if f"{prefix}+14d" in already_sent:
        return None
    if days_since >= second:
        return f"{prefix}+14d"
    if days_since >= first and f"{prefix}+3d" not in already_sent:
        return f"{prefix}+3d"
    return None


async def scan_for_nudges(now: datetime | None = None) -> list[NudgeItem]:
    """Cases due for a nudge — at most ONE item per case per scan.

    Chase first: an open case with a USER_CHASE-level missing document. Otherwise check-in
    (§11.5): audit complete, an actionable gameplan exists, and the user has neither reported
    an outcome nor told us how a call went. A case eligible for both gets the chase — the
    blocked audit is the sharper fact.
    """
    settings = get_settings()
    first, second = settings.nudge_first_days, settings.nudge_second_days
    now = _aware(now or datetime.now(timezone.utc))
    out: list[NudgeItem] = []

    async with AsyncSessionLocal() as s:
        cases = (
            await s.execute(select(CaseFile).where(CaseFile.status.in_(_OPEN_STATUSES)))
        ).scalars().all()
        for case in cases:
            findings = (
                await s.execute(select(Finding).where(Finding.case_file_id == case.case_file_id))
            ).scalars().all()
            times = [_aware(f.created_at) for f in findings if f.created_at is not None]
            if not times:
                continue  # no audit output yet → nothing to nudge about either way
            days_since = (now - min(times)).days
            ledger = list(case.nudges_sent or [])

            item: NudgeItem | None = None
            documents = _chase_documents(case.coverage)
            if documents:
                stage = _due_stage(days_since, ledger, first, second)
                if stage is not None:
                    item = NudgeItem(
                        user_id=str(case.user_id), case_file_id=str(case.case_file_id),
                        stage=stage, kind="chase", documents=documents, days_since=days_since,
                    )
            else:
                item = await _checkin_item(s, case, findings, days_since, ledger, first, second)

            if item is None:
                continue
            user = (
                await s.execute(select(User).where(User.user_id == case.user_id))
            ).scalar_one_or_none()
            item.email = user.email if user else None
            out.append(item)
    return out


async def _checkin_item(
    s, case: CaseFile, findings: list[Finding], days_since: int,
    ledger: list[str], first: int, second: int,
) -> NudgeItem | None:
    """The §11.5 check-in, when its premise actually holds (see the module docstring)."""
    if case.status != "audit_complete":
        return None  # his copy presumes a finished audit and a gameplan to act on
    if not any((f.recommendation or {}).get("action") or f.voice_tier == "C" for f in findings):
        return None  # no actionable step → nothing to check in about
    if case.last_outcome_check_at is not None:
        return None  # the user already told us how it went (call-mode tap or follow-up)

    from app.db.models.feedback import FeedbackEvent

    reported = (
        await s.execute(
            select(FeedbackEvent.id)
            .where(FeedbackEvent.case_file_id == case.case_file_id)
            .where(FeedbackEvent.feedback_type == "outcome_report")
            .limit(1)
        )
    ).first()
    if reported is not None:
        return None

    stage = _due_stage(days_since, ledger, first, second, prefix="checkin")
    if stage is None:
        return None

    # +14d cites {deadline_date}; pass it only from a PERSISTED pending deadline. None is
    # fine — _checkin_body degrades to the +3d string rather than inventing a date.
    deadline_date: str | None = None
    if stage == "checkin+14d":
        from app.db.models.deadlines import Deadline

        row = (
            await s.execute(
                select(Deadline.deadline_date)
                .where(Deadline.case_file_id == case.case_file_id)
                .where(Deadline.status == "pending")
                .order_by(Deadline.deadline_date)
                .limit(1)
            )
        ).scalar_one_or_none()
        deadline_date = row.isoformat() if row else None

    return NudgeItem(
        user_id=str(case.user_id), case_file_id=str(case.case_file_id),
        stage=stage, kind="checkin", days_since=days_since, deadline_date=deadline_date,
    )


async def _opted_out_users(user_ids: set[str]) -> set[str]:
    """The subset of users whose email_notifications_enabled is FALSE — reminders only;
    transactional mail never consults this (the split lives in app/notify/email.py)."""
    from uuid import UUID

    from app.db.models.users import User

    if not user_ids:
        return set()
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(User.user_id).where(
                    User.user_id.in_([UUID(u) for u in user_ids]),
                    User.email_notifications_enabled.is_(False),
                )
            )
        ).scalars().all()
    return {str(u) for u in rows}


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
    opted_out = await _opted_out_users({item.user_id for item in items})
    sent = 0
    skipped = 0
    for item in items:
        if not settings.enable_nudge_emails or not item.email:
            skipped += 1
            continue
        if item.user_id in opted_out:
            # The user's reminders preference (2026-08-19). Skip BEFORE send/mark so the
            # nudges_sent ledger stays unstamped — an opted-out user who opts back in must
            # not have silently burned their nudge stages.
            log.info(
                "nudge.skipped_by_preference",
                case_file_id=item.case_file_id, stage=item.stage, kind=item.kind,
            )
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
                # Suffix match, not equality — the check-in stages are "checkin+3d"/"checkin+14d",
                # and equality against "+3d" would have labeled every one of them "second".
                properties={
                    "stage": "first" if item.stage.endswith("+3d") else "second",
                    "kind": item.kind,
                },
            )
        else:
            skipped += 1
    return {"due": len(items), "sent": sent, "skipped": skipped}
