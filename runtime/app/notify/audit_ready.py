"""The audit-ready email — the thing §2.2 promises (D3, 2026-08-12).

Brock's §2.2 line is *"you can close this — I'll email you the moment it's ready."* It has
been authored and wired since 2026-08-11 but **withheld**, because we did not send that
email and a promise we don't keep strands the user worse than silence does. This module is
the email; once `enable_audit_ready_email` is on, the line renders itself (see
`routes/copy._leave_and_return_is_honest`).

**Both terminal outcomes send, on purpose.** A user who was told "I'll email you when it's
ready" and whose audit ends needing a document has still left and is still waiting. Emailing
only on success would keep the promise exactly when it's easy and break it exactly when the
user most needs to know — the close-the-loop failure X1 exists to prevent. So:

- `audit_complete`            → "your review is ready"
- `audit_incomplete` /
  `needs_documents`           → "I got as far as I could, here's the one thing I need"
- `system_error`              → **no email.** We don't push a failure into someone's inbox
                                with nothing for them to do; the thread says it and the
                                admin System page is alerted.

**PHI discipline (DL-47).** Nothing about the bill goes in the message: no amount, provider,
date of service, claim number, document type, or finding. The email says a review finished
and to sign in. `send_product_email` runs the guard over every one of these regardless.

**Idempotency.** `case_files.audit_ready_email_sent_at` is stamped only after SendGrid
accepts, so a failed send retries on the next terminal transition instead of being lost —
the bug the nudge ledger had.
"""

from __future__ import annotations

import datetime
from uuid import UUID

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.notify.email import FOOTER, send_product_email

log = structlog.get_logger(__name__)

# Terminal statuses that mean "we finished and the user should come look". system_error is
# deliberately absent — see the module docstring.
_READY = "audit_complete"
_NEEDS_DOCS_REASON = "needs_documents"

_SUBJECT_READY = "Your Tyndale review is ready"
_SUBJECT_NEEDS_DOCS = "One thing would finish your Tyndale review"


def _bodies(ready: bool, app_url: str) -> tuple[str, str, str]:
    """(subject, text, html). PHI-free by construction — nothing case-specific is
    interpolated, only the sign-in URL."""
    if ready:
        subject = _SUBJECT_READY
        lead = (
            "Your review is done — the numbers and everything I found are waiting for you."
        )
    else:
        subject = _SUBJECT_NEEDS_DOCS
        lead = (
            "I got as far as I could on your review. There's one document I still need "
            "before I can finish the numbers — it's listed in the app."
        )
    text = f"{lead}\n\nSign in to see it: {app_url}\n\n{FOOTER}\n"
    html = (
        f"<p>{lead}</p>"
        f'<p><a href="{app_url}" '
        'style="display:inline-block;background:#1F4E4A;color:#fff;padding:12px 20px;'
        'border-radius:8px;text-decoration:none;font-weight:600">Open Tyndale</a></p>'
        f'<p style="color:#667">{FOOTER}</p>'
    )
    return subject, text, html


def should_send(status: str, incomplete_reason: str | None) -> bool:
    """Which terminal transitions earn an email. Pure, so the policy is directly testable."""
    if status == _READY:
        return True
    return status == "audit_incomplete" and incomplete_reason == _NEEDS_DOCS_REASON


async def send_audit_ready_email(case_file_id: str) -> bool:
    """Send the audit-ready (or needs-documents) email for a case, once. Returns True if a
    message was accepted by SendGrid.

    Safe to call on every terminal transition: it re-reads the case, applies `should_send`,
    honours the flag, and no-ops if one was already sent.
    """
    settings = get_settings()
    if not settings.enable_audit_ready_email:
        return False

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        if case is None or case.audit_ready_email_sent_at is not None:
            return False
        if not should_send(case.status, case.audit_incomplete_reason):
            return False
        user = (
            await s.execute(select(User).where(User.user_id == case.user_id))
        ).scalar_one_or_none()
        email = (user.email or "").strip() if user else ""
        # A blocked or soft-deleted account is not someone we mail.
        if not email or (user is not None and (user.is_blocked or user.soft_deleted_at)):
            return False
        ready = case.status == _READY

    subject, text, html = _bodies(ready, settings.auth_success_redirect)
    sent = await send_product_email(email, subject, text, html, kind="audit_ready")
    if not sent:
        # Not stamped — the next terminal transition (or a re-audit) tries again. A lost
        # email is worse than a duplicate attempt at the same state.
        return False

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == UUID(case_file_id)))
        ).scalar_one_or_none()
        if case is not None and case.audit_ready_email_sent_at is None:
            case.audit_ready_email_sent_at = datetime.datetime.now(datetime.timezone.utc)
            await s.commit()
    log.info("notify.audit_ready.sent", case_file_id=case_file_id, ready=ready)
    return True
