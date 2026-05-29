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

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

log = structlog.get_logger(__name__)


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Server-side: always log the full traceback.
        log.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            exc_type=type(exc).__name__,
        )

        settings = get_settings()
        if settings.is_production:
            return JSONResponse(
                status_code=500,
                content={"error": "internal_server_error", "detail": "An unexpected error occurred."},
            )

        # Dev / staging — surface the traceback to the caller too.
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "exc_type": type(exc).__name__,
                "detail": str(exc),
                "traceback": traceback.format_exc().splitlines(),
            },
        )
