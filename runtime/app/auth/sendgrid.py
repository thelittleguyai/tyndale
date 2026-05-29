"""SendGrid magic-link email (Phase 2K).

Sends the sign-in link via SendGrid's Email API Pro tier (BAA-eligible per
DL-18). When SENDGRID_API_KEY is unset (local dev), logs the link instead of
sending — so the magic-link flow is exercisable end-to-end without SendGrid.

PHI-safe logging: we log only that a link was sent + the recipient domain in
production; the full URL (which contains the token) is logged ONLY when
sending is stubbed in dev.
"""

from __future__ import annotations

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_SENDGRID_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"
_SUBJECT = "Sign in to Tyndale"
_FOOTER = (
    "Tyndale provides medical billing and coverage advocacy, not medical, legal, "
    "or financial advice. If you didn't request this link, you can ignore this email."
)


def _bodies(magic_link_url: str) -> tuple[str, str]:
    text = (
        "Sign in to Tyndale\n\n"
        "Click the link below to sign in. It expires in 15 minutes and can be used once.\n\n"
        f"{magic_link_url}\n\n"
        f"{_FOOTER}\n"
    )
    html = (
        "<h2>Sign in to Tyndale</h2>"
        "<p>Click the button below to sign in. It expires in 15 minutes and can be used once.</p>"
        f'<p><a href="{magic_link_url}" '
        'style="display:inline-block;background:#1F4E4A;color:#fff;padding:12px 20px;'
        'border-radius:8px;text-decoration:none;font-weight:600">Sign in to Tyndale</a></p>'
        f'<p style="color:#667">{_FOOTER}</p>'
    )
    return text, html


async def send_magic_link_email(email: str, magic_link_url: str) -> None:
    settings = get_settings()
    key = (settings.sendgrid_api_key or "").strip()

    if not key or key.startswith("<"):
        # Dev stub — never send; log the URL so the flow is testable locally.
        log.warning("auth.magic_link.dev_stub_no_send", email=email, magic_link_url=magic_link_url)
        return

    text, html = _bodies(magic_link_url)
    payload = {
        "personalizations": [{"to": [{"email": email}]}],
        "from": {"email": settings.sendgrid_from_email, "name": "Tyndale"},
        "subject": _SUBJECT,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html", "value": html},
        ],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _SENDGRID_ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
    # SendGrid returns 202 on accept. Never log the token/URL in the real path.
    domain = email.split("@")[-1] if "@" in email else "?"
    if resp.status_code not in (200, 202):
        log.error("auth.magic_link.send_failed", status=resp.status_code, to_domain=domain)
        raise RuntimeError(f"SendGrid send failed: {resp.status_code}")
    log.info("auth.magic_link.sent", to_domain=domain)
