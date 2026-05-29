"""Dev-mode auth stub.

Every request resolves to a fixed dev user. The user row is created on
first request if it's missing (idempotent), so the FK constraints on
case_files / findings / deadlines all resolve cleanly even on a freshly-
migrated database.

# TODO(Phase 2K): replace this dependency with real JWT validation from
# Google + Email magic-link auth. The CurrentUser shape and the
# ``current_user`` dependency name should stay stable so callers don't
# need to be updated.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import User
from app.db.session import get_session

# Stable dev identifiers. Email is the real Google account so Phase 2K's
# Google sign-in flow lands the same user row (Google sign-in matches by
# verified email; the UUID stays whatever the database has assigned to that
# email's first sign-in).
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000d2")
DEV_USER_EMAIL = "pfluegelcx@gmail.com"
DEV_USER_FIRST_NAME = "Phil"
DEV_USER_TYPE = "admin"


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    email: str
    first_name: str
    user_type: str = "user"


async def _ensure_dev_user_row(s: AsyncSession) -> None:
    """Idempotent insert of the dev user row.

    On re-runs we also backfill ``user_type`` and ``email`` so changing them
    in this module's constants is enough — no need to manually delete the
    row in dev databases.
    """
    row = (await s.execute(select(User).where(User.user_id == DEV_USER_ID))).scalar_one_or_none()
    if row is None:
        s.add(
            User(
                user_id=DEV_USER_ID,
                email=DEV_USER_EMAIL,
                user_type=DEV_USER_TYPE,
                service_consent=True,
                improvement_consent=False,
            )
        )
        await s.commit()
        return
    # Backfill in case the constants moved
    dirty = False
    if row.email != DEV_USER_EMAIL:
        row.email = DEV_USER_EMAIL
        dirty = True
    if row.user_type != DEV_USER_TYPE:
        row.user_type = DEV_USER_TYPE
        dirty = True
    if dirty:
        await s.commit()


async def current_user(session: AsyncSession = Depends(get_session)) -> CurrentUser:
    """FastAPI dependency that resolves the current user.

    Phase 2H: always returns the dev user (after ensuring its row exists).
    Phase 2K: swap to JWT validation from the Authorization header; this
    function's signature + return shape stay stable so routes don't change.
    """
    await _ensure_dev_user_row(session)
    return CurrentUser(
        user_id=DEV_USER_ID,
        email=DEV_USER_EMAIL,
        first_name=DEV_USER_FIRST_NAME,
        user_type=DEV_USER_TYPE,
    )
