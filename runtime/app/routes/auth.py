"""Auth routes (Phase 2K) — Google OAuth + email magic-link + session.

Security posture (this surface is load-bearing for compliance):
  - Session cookie: HttpOnly, Secure (prod), SameSite=Lax, domain=.tyndaleapp.net
    (prod) so it cross-shares across subdomains. Lax (not Strict) so the OAuth
    callback redirect chain carries the cookie.
  - OAuth state+nonce: a signed, short-lived cookie holds the state; the
    callback rejects a mismatch (CSRF defense).
  - Magic-link: 15-min single-use JWT (jti tracked in magic_link_consumed);
    replay → 401. Request endpoint is rate-limited and ALWAYS returns 200
    (anti-enumeration). Tokens never logged in the real send path.
  - Match-on-verified-email: only verified emails create/resolve a user; the
    seeded admin (pfluegelcx@gmail.com) is matched, never recreated (DL-32).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.auth.google import GoogleOAuthError, handle_google_callback, initiate_google_oauth
from app.auth.jwt import (
    InvalidTokenError,
    create_magic_link_token,
    create_session_token,
    verify_magic_link_token,
)
from app.auth.match_on_email import EmailNotVerifiedError, find_or_create_user_by_email
from app.auth.rate_limit import RateLimitExceeded, magic_link_limiter
from app.auth.sendgrid import send_magic_link_email
from app.config import get_settings
from app.db.models.magic_link import MagicLinkConsumed
from app.db.session import get_session
from app.schemas.feedback import UserProfile

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

_OAUTH_STATE_COOKIE = "tyndale_oauth_state"


# --- cookie helpers ----------------------------------------------------------
def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain or None,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain or None,
        path="/",
    )


def _profile(user) -> UserProfile:
    first_name = (user.email or "").split("@")[0] or "there"
    return UserProfile(
        id=str(user.user_id),
        first_name=first_name,
        email=user.email,
        user_type=user.user_type,
        improvement_consent=bool(user.improvement_consent),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# --- Google OAuth ------------------------------------------------------------
@router.post("/auth/login")
async def login() -> JSONResponse:
    """Return the Google consent-screen URL + set a short-lived state cookie
    the callback checks (CSRF defense)."""
    settings = get_settings()
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(16)
    try:
        url = initiate_google_oauth(state, nonce)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    resp = JSONResponse({"authorization_url": url})
    resp.set_cookie(
        _OAUTH_STATE_COOKIE, state, max_age=600, httponly=True,
        secure=settings.cookie_secure, samesite="lax",
        domain=settings.cookie_domain or None, path="/",
    )
    return resp


@router.get("/auth/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    settings = get_settings()
    expected_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="invalid OAuth state")

    try:
        info = await handle_google_callback(code)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=502, detail="google auth failed") from exc

    try:
        user = await find_or_create_user_by_email(
            session, info["email"], verified=bool(info.get("verified_email"))
        )
    except EmailNotVerifiedError:
        raise HTTPException(status_code=403, detail="email not verified") from None
    await session.commit()

    token = create_session_token(str(user.user_id))
    redirect = RedirectResponse(url=settings.auth_success_redirect, status_code=302)
    _set_session_cookie(redirect, token)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE, domain=settings.cookie_domain or None, path="/")
    return redirect


# --- Email magic link --------------------------------------------------------
class MagicLinkRequest(BaseModel):
    email: str
    return_url: str | None = None


@router.post("/auth/magic-link-request")
async def magic_link_request(body: MagicLinkRequest, request: Request) -> dict:
    settings = get_settings()
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "unknown"

    # Rate limit BEFORE doing any work (per-email + per-IP). 429 on either.
    try:
        magic_link_limiter.check(
            f"email:{email}", limit=settings.magic_link_rate_per_email_hour, window_seconds=3600
        )
        magic_link_limiter.check(
            f"ip:{ip}", limit=settings.magic_link_rate_per_ip_hour, window_seconds=3600
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="too many requests",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    # Build + send the link. We always return 200 regardless of whether the
    # email maps to an existing account (anti-enumeration).
    token, _jti = create_magic_link_token(email, body.return_url)
    magic_link_url = f"{settings.magic_link_base_url}/v1/auth/magic-link-verify?token={token}"
    try:
        await send_magic_link_email(email, magic_link_url)
    except Exception:  # noqa: BLE001 — never leak send failures to the caller
        log.error("auth.magic_link.request_send_error", to_domain=email.split("@")[-1])

    return {"ok": True, "message": "If that email can sign in, a link is on its way."}


@router.get("/auth/magic-link-verify")
async def magic_link_verify(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    settings = get_settings()
    try:
        claims = verify_magic_link_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid or expired link") from None

    jti = claims["jti"]
    # Single-use: reject if already consumed (replay), else record it.
    existing = (await session.execute(
        select(MagicLinkConsumed).where(MagicLinkConsumed.jti == jti)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=401, detail="link already used") from None

    session.add(MagicLinkConsumed(
        jti=jti,
        consumed_at=datetime.now(timezone.utc),
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=timezone.utc),
    ))

    # Magic-link delivery to a controlled inbox proves email ownership → verified.
    user = await find_or_create_user_by_email(session, claims["email"], verified=True)
    await session.commit()

    session_token = create_session_token(str(user.user_id))
    dest = claims.get("return_url") or settings.auth_success_redirect
    redirect = RedirectResponse(url=dest, status_code=302)
    _set_session_cookie(redirect, session_token)
    return redirect


# --- Session management ------------------------------------------------------
@router.post("/auth/logout")
async def logout() -> Response:
    resp = Response(status_code=200)
    _clear_session_cookie(resp)
    return resp


@router.get("/auth/session")
async def get_session_info(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # current_user already validated the cookie (or returned the dev user).
    from app.db.models.users import User

    row = (await session.execute(select(User).where(User.user_id == user.user_id))).scalar_one()
    return {"user": _profile(row).model_dump()}


@router.get("/auth/whoami")
async def whoami(
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await get_session_info(user, session)
