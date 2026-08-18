"""The one outbound path for product email (2026-08-12).

Before this, the only mail that actually left the building was the magic link. The nudge
cron's "sender" ran the PHI guard, logged, and returned True **without calling SendGrid** —
so a case got stamped into its `nudges_sent` ledger while nothing was delivered, and the
ledger then prevented a retry forever. That's the failure this module closes.

Two invariants, both non-negotiable:

1. **Every send passes the DL-47 PHI guard first.** Product email is the least-controlled
   surface we have — it lands in an inbox we don't own, gets forwarded, gets indexed by a
   mail provider. Copy here names document TYPES and states, never amounts, providers,
   diagnoses, or claim identifiers. The guard is the enforcement, not the convention.
2. **A send that didn't happen returns False.** Callers use the return value to decide
   whether to write their idempotency ledger, so "logged but not sent" must never look like
   success — that's exactly how the nudge silently lost its emails.

No SendGrid key (local dev) is an honest False, not a fake True: nothing was delivered.

THE REMINDER / TRANSACTIONAL SPLIT (2026-08-19, settings item 1):

  * REMINDERS — kind="nudge" (chase + check-in) — honor the user's
    `email_notifications_enabled` preference. The check lives at the CALLER (the nudge
    cron, which knows the user and skips BEFORE send/mark so ledgers stay unstamped).
  * TRANSACTIONAL — kind="audit_ready" / "recovery" (and the auth path's magic links) —
    are SERVICE MAIL: the direct consequence of an action the user just took or a promise
    the product just made. They never consult the preference; an opted-out user still
    gets "your review is ready", because silence there would break §2.2/§10.4 promises.

REMINDER_KINDS below is the split's single source; tests pin both sides.
"""

from __future__ import annotations

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

# The kinds that are REMINDERS (preference-gated at the caller). Everything else sent
# through this module is transactional service mail. See the module docstring.
REMINDER_KINDS = frozenset({"nudge"})

_SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"

FOOTER = (
    "Tyndale provides medical billing and coverage advocacy, not medical, legal, or "
    "financial advice."
)


def _to_domain(email: str) -> str:
    """The recipient's domain only — never the address — for PHI-safe logging."""
    return email.split("@")[-1] if "@" in email else "?"


# Synthetic-identity suffixes (settings.synthetic_email_suffixes — env-extendable so
# staging's test identities are coverable). `.test` is a reserved TLD — those addresses can
# NEVER deliver, and a full sweep completing ~15 audits fires ~15 real sends at them in
# under an hour: a textbook spam-trap signature that can get the SendGrid account
# flagged/paused (the 2026-08-18 sweep's mail-send 401s, while the same key answered 200 on
# read endpoints). Synthetic recipients never reach the provider.


async def send_product_email(
    to_email: str, subject: str, text: str, html: str | None = None, *, kind: str
) -> bool:
    """Send one transactional email. Returns True ONLY if SendGrid accepted it.

    `kind` is a short slug for logs/metrics ("audit_ready", "nudge") — it is never sent.
    """
    settings = get_settings()

    # DL-47 guard first, before a key check or a network call: a PHI leak must fail the same
    # way in dev as in prod, so the guard can't be something only production exercises.
    from app.hooks.pre_tool_use import evaluate_send_email

    decision = evaluate_send_email({"to": to_email, "subject": subject, "body": text})
    if not decision.approved:
        log.error("notify.blocked_by_phi_guard", kind=kind, reason=decision.block_reason)
        return False

    recipient = to_email.strip().lower()
    if any(recipient.endswith(s) for s in settings.synthetic_email_suffix_list):
        # False (nothing delivered) so exactly-once ledgers stay unstamped — the harness
        # asserts honest state, and a synthetic user re-completing retries harmlessly.
        log.info("notify.synthetic_recipient_no_send", kind=kind, to_domain=_to_domain(to_email))
        return False

    key = (settings.sendgrid_api_key or "").strip()
    if not key or key.startswith("<"):
        # Local dev: nothing is delivered, so this is False. The subject is safe to log (it
        # is PHI-free by construction and just passed the guard); the body is not logged.
        log.warning("notify.dev_stub_no_send", kind=kind, to_domain=_to_domain(to_email), subject=subject)
        return False

    content: list[dict[str, str]] = [{"type": "text/plain", "value": text}]
    if html:
        content.append({"type": "text/html", "value": html})
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": settings.sendgrid_from_email, "name": "Tyndale"},
        "subject": subject,
        "content": content,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _SENDGRID_ENDPOINT,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
    except Exception as exc:  # noqa: BLE001 — a send failure must never break the caller's flow
        log.error("notify.send_error", kind=kind, to_domain=_to_domain(to_email), error=str(exc))
        return False

    if resp.status_code not in (200, 202):
        log.error("notify.send_failed", kind=kind, status=resp.status_code, to_domain=_to_domain(to_email))
        return False
    log.info("notify.sent", kind=kind, to_domain=_to_domain(to_email))
    return True
