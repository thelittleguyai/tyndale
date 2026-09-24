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
from urllib.parse import urlencode, urljoin, urlsplit

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.auth.google import GoogleOAuthError, handle_google_callback, initiate_google_oauth
from app.auth.jwt import (
    ExpiredLinkError,
    renewable_magic_link_claims,
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
    # Write the effective name (__Secure-tyndale_session over HTTPS;
    # tyndale_session on plain-http dev). current_user reads BOTH names so
    # existing tyndale_session cookies keep working through the grace period.
    response.set_cookie(
        key=settings.session_cookie_write_name,
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
    # Clear every accepted name (new + legacy) so logout fully signs out.
    for name in settings.session_cookie_read_names:
        response.delete_cookie(
            key=name,
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

    token = create_session_token(str(user.user_id), user.jwt_version or 1)
    redirect = RedirectResponse(url=await _landing(session, user.user_id, None), status_code=302)
    _set_session_cookie(redirect, token)
    redirect.delete_cookie(_OAUTH_STATE_COOKIE, domain=settings.cookie_domain or None, path="/")
    return redirect


# --- Email magic link --------------------------------------------------------
def _safe_return_path(value: object) -> str | None:
    """MEDIUM-2 (2026-08-19 security review): return_url rides inside the SIGNED magic-link
    token, but its VALUE originates from the unauthenticated request — unvalidated, it is an
    open redirect off our origin the moment the victim clicks a genuine link. Accept only a
    same-origin RELATIVE path: exactly one leading '/', no scheme, no protocol-relative
    '//host', no backslash (browser URL parsers normalize '\\' to '/', so '/\\evil.com'
    becomes '//evil.com'), no control characters. Anything else reads as absent and the
    caller falls back to the default post-login path."""
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return None
    if "\\" in value or any(ord(c) < 0x20 for c in value):
        return None
    return value


def _app_url(path: str) -> str:
    """A same-origin relative path, on the APP's origin (auth_success_redirect's). The verify
    link is served by the API host (api.tyndaleapp.net on dev), so a bare "/intake" Location
    would land on the API, not the app."""
    base = urlsplit(get_settings().auth_success_redirect)
    return urljoin(f"{base.scheme}://{base.netloc}", path)


async def _landing(session: AsyncSession, user_id, return_url: object) -> str:
    """Where a fresh sign-in lands. An explicit safe return path wins; else a guided case the
    user left unfinished resumes on /intake at the planner's next screen (doc 40 decision 7:
    the resume path — never the dashboard); else the default post-login page."""
    safe = _safe_return_path(return_url)
    if safe:
        return _app_url(safe)
    from app.db.models.case_files import CaseFile

    resume = (
        await session.execute(
            select(CaseFile.case_file_id)
            .where(CaseFile.user_id == user_id)
            .where(CaseFile.intake_mode == "guided")
            .where(CaseFile.intake_status == "in_progress")
            .where(CaseFile.soft_deleted_at.is_(None))
            .order_by(CaseFile.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if resume is not None:
        return _app_url(f"/intake?case={resume}")
    return get_settings().auth_success_redirect


def _email_hint(email: str) -> str:
    """"j•••@gmail.com" — enough to recognise the address, not to read it off a screen."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}•••@{domain}" if domain else "•••"


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
    # email maps to an existing account (anti-enumeration). An unsafe return_url is
    # never even signed into the token (verify re-checks regardless — tokens outlive code).
    token, _jti = create_magic_link_token(email, _safe_return_path(body.return_url))
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
    try:
        claims = verify_magic_link_token(token)
    except ExpiredLinkError:
        # An AUTHENTIC link past its 15 minutes (doc 40 decision 7): the app's sign-in screen,
        # which offers a new link in one tap — never a JSON 401 on the API host. The token goes
        # back in the query (it came in one): /magic-link-reissue re-checks it and mails the new
        # link to the address inside it, so nobody retypes it and the app never reads it.
        return RedirectResponse(
            url=_app_url("/sign-in") + "?" + urlencode({"link": "expired", "t": token}),
            status_code=302,
        )
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

    session_token = create_session_token(str(user.user_id), user.jwt_version or 1)
    # Enforced at CONSUME time too, not just at mint: already-issued tokens (and any
    # future mint path) stay constrained to same-origin relative paths — resolved on the app.
    redirect = RedirectResponse(url=await _landing(session, user.user_id, claims.get("return_url")), status_code=302)
    _set_session_cookie(redirect, session_token)
    return redirect


class MagicLinkReissue(BaseModel):
    token: str


@router.post("/auth/magic-link-reissue")
async def magic_link_reissue(body: MagicLinkReissue, request: Request) -> dict:
    """An authentic link that EXPIRED (within MAGIC_LINK_RENEWABLE_FOR) → a fresh one to the
    SAME address with the SAME destination (doc 40 decision 7: the resume path re-issues
    cleanly). The address rides inside the signed token — the caller neither types nor sees
    it; the answer names it only as a hint. Rate-limited exactly like a request."""
    settings = get_settings()
    try:
        claims = renewable_magic_link_claims(body.token)
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="that link can't be renewed — enter your email") from None
    email = claims["email"]
    ip = request.client.host if request.client else "unknown"
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
    token, _jti = create_magic_link_token(email, _safe_return_path(claims.get("return_url")))
    magic_link_url = f"{settings.magic_link_base_url}/v1/auth/magic-link-verify?token={token}"
    try:
        await send_magic_link_email(email, magic_link_url)
    except Exception:  # noqa: BLE001 — never leak send failures to the caller
        log.error("auth.magic_link.reissue_send_error", to_domain=email.split("@")[-1])
    return {"ok": True, "email_hint": _email_hint(email)}


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
