"""PHI-safe structured request logger.

Logs method, path, status, and duration ONLY. Request and response bodies are
never logged (they may contain PHI). This holds even at the scaffold stage.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = structlog.get_logger(__name__)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Correlate logs + error responses across a single request (Phase 2K.2).
        # Honor an inbound X-Request-ID (e.g. from the LB) or mint one.
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers.setdefault("X-Request-ID", request_id)
        # NOTE: deliberately no request/response body in the log payload (PHI-safe).
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
