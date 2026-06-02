"""The current_user FastAPI dependency (Phase 2K).

USE_REAL_AUTH=true  → validate the session cookie (HS256 JWT, audience
                      'session'); load the user row by id; 401 on any failure.
USE_REAL_AUTH=false → return the seeded dev/admin user (preserves Phase 2H
                      local-dev behavior without Google creds).

Routes import this via `from app.auth import current_user`. Its return shape
(CurrentUser) is unchanged from the dev stub, so no route code changed.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dev_user import CurrentUser, resolve_dev_user
from app.auth.jwt import InvalidTokenError, verify_session_claims
from app.config import get_settings
from app.db.models.users import User
from app.db.session import get_session


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    settings = get_settings()

    if not settings.use_real_auth:
        return await resolve_dev_user(session)

    # Read the new __Secure- name OR the legacy name (grace period, DL-46) so
    # the cutover doesn't log existing sessions out.
    token = None
    for name in settings.session_cookie_read_names:
        token = request.cookies.get(name)
        if token:
            break
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        user_id, token_version = verify_session_claims(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid or expired session") from None

    import uuid

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid session subject") from None

    row = (await session.execute(select(User).where(User.user_id == uid))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="user not found") from None

    # CO-9: enforce account status + session-revocation before granting access.
    enforce_user_access(row, token_version)

    # first_name isn't a column; derive from email local-part for now (real
    # name comes from the OAuth profile when we persist it — Phase 3 polish).
    first_name = (row.email or "").split("@")[0] or "there"
    return CurrentUser(
        user_id=row.user_id,
        email=row.email,
        first_name=first_name,
        user_type=row.user_type,
    )


def enforce_user_access(row: User, token_version: int | None) -> None:
    """Raise if the user can't transact (CO-9). Soft-deleted → 401; blocked → 403; a
    session token whose version is stale vs the user's jwt_version → 401 (revoked).

    Pure + standalone so the security property is unit-testable without real-auth plumbing
    (the dev-user path in current_user bypasses this, matching prior local-dev behavior).
    """
    if row.soft_deleted_at is not None:
        raise HTTPException(
            status_code=401, detail={"code": "USER_DELETED", "reason": "account_deleted"}
        )
    if row.is_blocked:
        raise HTTPException(
            status_code=403,
            detail={"code": "USER_BLOCKED", "reason": row.blocked_reason or "blocked"},
        )
    if token_version is not None and token_version < (row.jwt_version or 1):
        raise HTTPException(
            status_code=401, detail={"code": "JWT_INVALIDATED", "reason": "session_revoked"}
        )
