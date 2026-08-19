"""JSON-shaped error responses.

MEDIUM-6 (2026-08-19 security review): the OPAQUE body (correlation_id only) is the
default in EVERY env. Verbose bodies (exc type/message/traceback) require the explicit
DEBUG_ERROR_RESPONSES opt-in and are hard-forced off in staging/production regardless
of the flag (settings.error_responses_verbose) — a traceback can carry PHI, and "not
production" is not a safety boundary once an env is publicly reachable. Local dev sets
the flag in .env so the curl/browser debug loop still sees the actual exception.

Either way, ``log.exception`` writes the full structlog-formatted traceback to the
server log, so the correlation_id always resolves to a full trace server-side.
"""

from __future__ import annotations

import traceback
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

log = structlog.get_logger(__name__)


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Phase 2K.2: tie the (opaque) client response to the full server-side
        # traceback via a correlation_id, so engineers can look it up in the
        # structured log without ever leaking exception detail to the caller.
        correlation_id = uuid.uuid4().hex
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            "x-request-id"
        ) or uuid.uuid4().hex

        log.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            exc_type=type(exc).__name__,
            correlation_id=correlation_id,
            request_id=request_id,
        )

        settings = get_settings()
        if not settings.error_responses_verbose:
            # Default everywhere: NO exception type/message/traceback in the body —
            # correlation_id only (it resolves to the full trace in the server log).
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "detail": "An unexpected error occurred.",
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                },
            )

        # DEBUG_ERROR_RESPONSES opt-in, non-public env only — the curl/browser debug loop
        # sees the actual exception (DL-29's intent, behind an explicit flag now).
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "exc_type": type(exc).__name__,
                "detail": str(exc),
                "correlation_id": correlation_id,
                "request_id": request_id,
                "traceback": traceback.format_exc().splitlines(),
            },
        )
