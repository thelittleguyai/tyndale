"""Allowlist of email templates vetted as PHI-free BY CONSTRUCTION (Phase CO-8 / DL-47).

An email whose ``template_id`` is in ``ALLOWED_TEMPLATE_IDS`` skips the deep PHI
scan in the send_email PreToolUse guardrail: its content is account-management /
generic-notification language only, reviewed so its variable substitutions can
never interpolate a bill amount, diagnosis, code, or any case detail. Anything
NOT on this list goes through ``detect_phi()`` over subject + body.

Adding a template: see ``intelligence-layer/reference/no_phi_in_emails.md``
("Adding a new template"). The bar is "variable substitution can NEVER produce PHI".
"""

from __future__ import annotations

ALLOWED_TEMPLATE_IDS: frozenset[str] = frozenset(
    {
        # Auth + account templates (verified PHI-free by construction)
        "magic_link_signin",
        "magic_link_signup",
        "email_verification",
        "welcome_email",
        "password_reset",  # for the future if password auth lands
        "session_expired",
        "account_deleted_confirmation",
        # Generic product notifications (verified PHI-free by construction)
        "report_ready",  # "Your report is ready — sign in to see it." NO amounts/diagnosis/detail.
        "case_update_available",  # "There's an update on one of your cases." NO specifics.
        "deadline_reminder_generic",  # "You have a deadline coming up. Sign in." NO specifics.
        # Operational (ops/admin only)
        "admin_alert",  # routes to Brock; system messages only
    }
)


def is_allowlisted(template_id: str | None) -> bool:
    """True iff ``template_id`` names a vetted PHI-free template (deep scan skipped)."""
    return template_id is not None and template_id in ALLOWED_TEMPLATE_IDS
