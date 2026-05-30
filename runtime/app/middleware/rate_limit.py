"""Application-wide rate limiting (Phase 2K.2 / DL-46).

Now that the runtime is public at api.tyndaleapp.net (DL-42), every route gets a
baseline limit. Reuses the in-memory SlidingWindowRateLimiter from Phase 2K.

  PERSISTENCE: in-memory, PER-REPLICA. With >1 Container App replica these
  limits are per-replica, not global — acceptable for V1-Lite traffic. Phase 4
  swaps the backing store for Redis to make them global (security/HIPAA contact).

Limits (all env-configurable):
  - Per-IP baseline (all traffic):           100/min + 1000/hr
  - Per-user baseline (authenticated only):  200/min + 2000/hr
  - Per-route hourly caps on expensive POSTs (per user when authed, else per IP):
      /v1/upload, /v1/audit/{id}/extract, /v1/audit/{id}/finalize  → 20/hr
      /v1/audit/{id}/confirmations                                 → 50/hr
  - /v1/auth/magic-link-request keeps its own per-email + per-IP limiter at the
    route level (Phase 2K) — not duplicated here.

429 + Retry-After on a hit. /health is exempt (Container Apps probes). Disabled
wholesale via RATE_LIMIT_ENABLED=false (the test suite sets this).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.jwt import InvalidTokenError, verify_session_token
from app.auth.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from app.config import get_settings
from app.middleware.net import client_ip

# Module singleton so every request shares the window (per replica).
global_limiter = SlidingWindowRateLimiter()

_EXEMPT_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}


def _route_cap(method: str, path: str, settings) -> tuple[str, int] | None:
    """(route_key, hourly_limit) for expensive POSTs, else None."""
    if method != "POST":
        return None
    if path == "/v1/upload":
        return ("upload", settings.rate_limit_upload_per_hour)
    if path.startswith("/v1/audit/"):
        if path.endswith("/extract"):
            return ("extract", settings.rate_limit_extract_per_hour)
        if path.endswith("/finalize"):
            return ("finalize", settings.rate_limit_finalize_per_hour)
        if path.endswith("/confirmations"):
            return ("confirmations", settings.rate_limit_confirmations_per_hour)
    return None


def _principal(request: Request, settings) -> str | None:
    """Best-effort authenticated user_id from the session cookie (never raises).
    Used to key per-user limits; anonymous traffic is counted by IP only."""
    if not settings.use_real_auth:
        return None
    for name in settings.session_cookie_read_names:
        token = request.cookies.get(name)
        if not token:
            continue
        try:
            return verify_session_token(token)
        except InvalidTokenError:
            continue
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if (
            not settings.rate_limit_enabled
            or request.method == "OPTIONS"
            or request.url.path in _EXEMPT_PATHS
        ):
            return await call_next(request)

        ip = client_ip(request, settings.trust_forwarded_for_hops)
        user_id = _principal(request, settings)

        try:
            global_limiter.check(f"ip:min:{ip}", limit=settings.rate_limit_per_ip_per_minute, window_seconds=60)
            global_limiter.check(f"ip:hr:{ip}", limit=settings.rate_limit_per_ip_per_hour, window_seconds=3600)
            if user_id:
                global_limiter.check(f"user:min:{user_id}", limit=settings.rate_limit_per_user_per_minute, window_seconds=60)
                global_limiter.check(f"user:hr:{user_id}", limit=settings.rate_limit_per_user_per_hour, window_seconds=3600)
            cap = _route_cap(request.method, request.url.path, settings)
            if cap:
                route_key, limit = cap
                subject = f"user:{user_id}" if user_id else f"ip:{ip}"
                global_limiter.check(f"route:{route_key}:{subject}", limit=limit, window_seconds=3600)
        except RateLimitExceeded as exc:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "detail": "Too many requests. Slow down and retry."},
                headers={"Retry-After": str(exc.retry_after_seconds)},
            )

        return await call_next(request)
