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

# Stable dev identifiers. Different UUID from the upload-route's dev user
# so we don't collide with cases created via the Phase 2D walking skeleton
# under USE_REAL_CLAUDE=false / no auth.
_DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000d2")
_DEV_USER_EMAIL = "phil@tyndaleapp.local"
_DEV_USER_FIRST_NAME = "Phil"


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    email: str
    first_name: str


async def _ensure_dev_user_row(s: AsyncSession) -> None:
    """Idempotent insert of the dev user row."""
    row = (await s.execute(select(User).where(User.user_id == _DEV_USER_ID))).scalar_one_or_none()
    if row is not None:
        return
    s.add(
        User(
            user_id=_DEV_USER_ID,
            email=_DEV_USER_EMAIL,
            service_consent=True,
            improvement_consent=False,
        )
    )
    await s.commit()


async def current_user(session: AsyncSession = Depends(get_session)) -> CurrentUser:
    """FastAPI dependency that resolves the current user.

    Phase 2H: always returns the dev user (after ensuring its row exists).
    Phase 2K: swap to JWT validation from the Authorization header.
    """
    await _ensure_dev_user_row(session)
    return CurrentUser(
        user_id=_DEV_USER_ID,
        email=_DEV_USER_EMAIL,
        first_name=_DEV_USER_FIRST_NAME,
    )
