"""Match-on-verified-email (Phase 2K / DL-32).

When an auth provider returns a VERIFIED email, look up the user by that
email (normalized to lowercase). If found, return it — NEVER changing the
existing user_type (so the seeded admin row for pfluegelcx@gmail.com keeps
its admin role through the auth swap with zero migration). If not found,
create a new user with the default user_type ('user').

A non-verified email is refused outright — we never auto-create or log in
an account from an unverified address.
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import User

log = structlog.get_logger(__name__)


class EmailNotVerifiedError(Exception):
    """The provider did not assert the email is verified."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def find_or_create_user_by_email(
    session: AsyncSession,
    email: str,
    *,
    verified: bool,
    default_user_type: str = "user",
) -> User:
    if not verified:
        raise EmailNotVerifiedError(f"email {email!r} is not verified")
    norm = normalize_email(email)

    # Case-insensitive match (defensive — providers usually lowercase already).
    row = (
        await session.execute(select(User).where(func.lower(User.email) == norm))
    ).scalar_one_or_none()
    if row is not None:
        # Existing user — do NOT touch user_type (DL-32). Just return.
        log.info("auth.match_on_email.found", user_id=str(row.user_id), user_type=row.user_type)
        return row

    # New user — default role, consent off by default (L05).
    user = User(
        email=norm,
        user_type=default_user_type,
        service_consent=True,
        improvement_consent=False,
    )
    session.add(user)
    await session.flush()  # populate user.user_id
    log.info("auth.match_on_email.created", user_id=str(user.user_id), user_type=default_user_type)
    return user
