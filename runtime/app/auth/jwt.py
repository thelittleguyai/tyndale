"""JWT helpers for session + magic-link tokens (Phase 2K).

HS256 signed with settings.auth_secret. Two token audiences, never
interchangeable:
  - "session"     — long-lived (settings.session_ttl_hours), sub = user_id.
  - "magic_link"  — short-lived (settings.magic_link_ttl_minutes), single-use
                    (jti tracked in magic_link_consumed), carries email + return_url.

Every verify checks signature + expiry + audience + issuer. A token with the
wrong audience (e.g. a magic-link token presented as a session cookie) is
rejected — this is deliberate defense against token-type confusion.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import get_settings

_ISSUER = "tyndale"
_ALGO = "HS256"
_AUD_SESSION = "session"
_AUD_MAGIC = "magic_link"


class InvalidTokenError(Exception):
    """Raised when a token fails any validation check."""


def _secret() -> str:
    settings = get_settings()
    if not settings.has_real_auth_secret():
        raise InvalidTokenError("AUTH_SECRET is not configured")
    return settings.auth_secret  # type: ignore[return-value]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Session tokens ----------------------------------------------------------
def create_session_token(user_id: str) -> str:
    settings = get_settings()
    iat = _now()
    payload = {
        "sub": str(user_id),
        "iss": _ISSUER,
        "aud": _AUD_SESSION,
        "iat": iat,
        "exp": iat + timedelta(hours=settings.session_ttl_hours),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def verify_session_token(token: str) -> str:
    """Returns the user_id (sub) or raises InvalidTokenError."""
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[_ALGO],  # explicit allow-list — defeats alg-confusion ("none"/RS256)
            audience=_AUD_SESSION,  # a magic-link token (aud=magic_link) is rejected here
            issuer=_ISSUER,
            options={
                "require": ["exp", "iat", "sub", "aud", "iss"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except jwt.PyJWTError as exc:  # expired, bad sig, wrong aud/iss, missing claim
        raise InvalidTokenError(str(exc)) from exc
    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("missing sub")
    return str(sub)


# --- Magic-link tokens -------------------------------------------------------
def create_magic_link_token(email: str, return_url: str | None) -> tuple[str, str]:
    """Returns (token, jti). The jti is recorded as consumed on verify."""
    settings = get_settings()
    iat = _now()
    jti = uuid.uuid4().hex
    payload = {
        "email": email.strip().lower(),
        "return_url": return_url,
        "jti": jti,
        "iss": _ISSUER,
        "aud": _AUD_MAGIC,
        "iat": iat,
        "exp": iat + timedelta(minutes=settings.magic_link_ttl_minutes),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO), jti


def verify_magic_link_token(token: str) -> dict[str, Any]:
    """Returns {email, return_url, jti, exp} or raises InvalidTokenError.

    Does NOT check single-use consumption — the route checks the
    magic_link_consumed table (the DB is the source of truth for replay).
    """
    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[_ALGO],
            audience=_AUD_MAGIC,  # a session token (aud=session) is rejected here
            issuer=_ISSUER,
            options={
                "require": ["exp", "iat", "jti", "aud", "iss", "email"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return {
        "email": str(payload["email"]).strip().lower(),
        "return_url": payload.get("return_url"),
        "jti": payload["jti"],
        "exp": payload["exp"],
    }
