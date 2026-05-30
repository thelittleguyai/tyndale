"""Security response headers (Phase 2K.2 / DL-46).

Applied to every response now that the runtime is public. HSTS + clickjacking +
MIME-sniff + referrer + permissions hardening. Non-HTML (API) responses also get
a strict CSP; HTML responses (the OAuth callback redirect) skip CSP since that
body is minimal and trusted. Disable via SECURITY_HEADERS_ENABLED=false.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings

_BASE_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "X-DNS-Prefetch-Control": "off",
}
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not get_settings().security_headers_enabled:
            return response
        for key, value in _BASE_HEADERS.items():
            response.headers.setdefault(key, value)
        if "text/html" not in response.headers.get("content-type", "").lower():
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
        return response
