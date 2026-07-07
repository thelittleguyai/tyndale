"""Admin-only, DEV-ONLY test support (HP-2): mint a session token for a SYNTHETIC test user so
the e2e scenario harness can drive the real API as an isolated, non-real identity.

Belt AND suspenders — three independent gates:
  * admin_user      — a non-admin gets 404 (DL-60 anti-enumeration).
  * NOT production   — 404 when is_production, so the endpoint effectively does not exist in prod.
  * synthetic email  — the address MUST end with the e2e suffix, so a token can NEVER be minted
                       for a real user through this path.
This is not a general impersonation tool: it only ever issues a token for a synthetic test user.
"""

from __future__ import annotations

import hmac

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.auth.jwt import InvalidTokenError, create_session_token
from app.config import get_settings
from app.db.models.users import User
from app.db.session import get_session

router = APIRouter(tags=["admin"])
log = structlog.get_logger(__name__)

# Synthetic identities ONLY — a token can never be minted for a real user through this path.
SYNTHETIC_EMAIL_SUFFIX = "@e2e.tyndale.test"


class TestTokenRequest(BaseModel):
    email: str


class TestTokenResponse(BaseModel):
    token: str
    user_id: str
    email: str
    cookie_name: str


async def _authorize_test_token(
    request: Request, session: AsyncSession = Depends(get_session)
) -> str:
    """Authorize the caller by EITHER path, and return a short label for logging:
      * 'e2e_secret' — the dev-only shared secret in the X-E2E-Test-Secret header (for CI: stable,
        no session needed). Constant-time compared; only honored when the secret is configured.
      * 'admin:<id>' — a logged-in admin session (the interactive path).
    404 in production, and 404 for any unauthorized caller (DL-60 — reveal nothing)."""
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not Found")
    secret = settings.e2e_test_token_secret
    provided = request.headers.get("X-E2E-Test-Secret")
    if secret and provided and hmac.compare_digest(provided, secret):
        return "e2e_secret"
    try:
        user = await current_user(request, session)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Not Found") from None
    if user.user_type != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    return f"admin:{user.user_id}"


@router.post("/admin/test-token", response_model=TestTokenResponse)
async def issue_test_token(
    body: TestTokenRequest,
    authorized_by: str = Depends(_authorize_test_token),
    session: AsyncSession = Depends(get_session),
) -> TestTokenResponse:
    # _authorize_test_token already enforced dev-only + (shared secret | admin session).
    settings = get_settings()
    email = body.email.strip().lower()
    if not email.endswith(SYNTHETIC_EMAIL_SUFFIX):
        raise HTTPException(
            status_code=400,
            detail=f"test-token is only for synthetic {SYNTHETIC_EMAIL_SUFFIX} identities",
        )

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, user_type="user")
        session.add(user)
        await session.flush()
    try:
        token = create_session_token(str(user.user_id))
    except InvalidTokenError as exc:
        # Local dev without AUTH_SECRET can't sign a session — a clean 503, not a 500. (The
        # harness driver falls back to the dev-user stub in this case.)
        await session.rollback()
        raise HTTPException(status_code=503, detail=f"cannot mint token: {exc}") from exc
    await session.commit()
    log.info("admin.test_token.issued", email=email, authorized_by=authorized_by)
    return TestTokenResponse(
        token=token,
        user_id=str(user.user_id),
        email=email,
        cookie_name=settings.session_cookie_write_name,
    )
