"""Request body size limits (Phase 2K.2 / DL-46).

Rejects oversized bodies with 413 based on Content-Length, before the body is
read into memory. Multipart uploads get the larger ceiling; everything else the
JSON cap. Per-file limits are enforced in the upload route (this bounds the
whole request). V1-Lite has no chunked upload — the only recourse on 413 is a
smaller file. Absent/chunked bodies (no Content-Length) fall through to route
validation + the ASGI server's own limits.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            settings = get_settings()
            is_multipart = "multipart/form-data" in request.headers.get("content-type", "").lower()
            limit = settings.max_request_body_bytes if is_multipart else settings.max_json_body_bytes
            if size > limit:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "payload_too_large",
                        "detail": (
                            f"Request body exceeds the {limit}-byte limit. Retry with a smaller "
                            "payload — V1-Lite does not support chunked upload."
                        ),
                    },
                )
        return await call_next(request)
