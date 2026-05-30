"""JSON-shaped error responses.

Dev / staging: the traceback IS returned in the response so curl + browsers
see the actual exception — the local debug loop is otherwise blind because
500 hides everything. Production: the response stays opaque ('an unexpected
error occurred'); the full traceback only lives in the server log.

Either way, ``log.exception`` writes the full structlog-formatted traceback
to the server log, so even in dev you have a permanent record.
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
        if settings.is_production:
            # Production: NO exception type/message/traceback in the body —
            # correlation_id only.
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "detail": "An unexpected error occurred.",
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                },
            )

        # Dev / staging — surface the traceback to the caller too (DL-29).
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
