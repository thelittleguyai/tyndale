"""Google OAuth 2.0 (Authorization Code) helpers (Phase 2K).

initiate_google_oauth(state) -> the consent-screen redirect URL.
handle_google_callback(code, ...) -> {email, verified_email, name}.

State + nonce CSRF protection: the caller mints a random state, stores it
(signed in a short-lived cookie or server-side), and verifies it matches on
callback before calling handle_google_callback. We request only openid+email+
profile scopes — the minimum to establish identity. We TRUST Google's
email_verified flag and pass it through to match-on-verified-email.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import get_settings

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
_SCOPES = "openid email profile"


class GoogleOAuthError(Exception):
    pass


def initiate_google_oauth(state: str, nonce: str) -> str:
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleOAuthError("GOOGLE_CLIENT_ID not configured")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "state": state,
        "nonce": nonce,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_AUTH_ENDPOINT}?{urlencode(params)}"


async def handle_google_callback(code: str) -> dict:
    """Exchange the auth code for tokens, fetch userinfo. Returns
    {email, verified_email, name}. Raises GoogleOAuthError on any failure."""
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret):
        raise GoogleOAuthError("Google OAuth not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            _TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise GoogleOAuthError(f"token exchange failed: {token_resp.status_code}")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise GoogleOAuthError("no access_token in token response")

        userinfo_resp = await client.get(
            _USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise GoogleOAuthError(f"userinfo failed: {userinfo_resp.status_code}")
        info = userinfo_resp.json()

    email = info.get("email")
    if not email:
        raise GoogleOAuthError("no email in userinfo")
    return {
        "email": email,
        # OIDC userinfo uses "email_verified"; trust Google's assertion.
        "verified_email": bool(info.get("email_verified", False)),
        "name": info.get("name") or info.get("given_name"),
    }
