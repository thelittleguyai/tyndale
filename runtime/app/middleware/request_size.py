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

# JSON endpoints that carry a base64-encoded image and so need the larger upload
# ceiling rather than the 1 MB JSON cap (CO-18). A small explicit allowlist — every
# other JSON body stays capped at max_json_body_bytes.
_IMAGE_UPLOAD_PATHS = ("/insurance/card/upload",)


def _is_image_upload_path(path: str) -> bool:
    return any(path.endswith(p) for p in _IMAGE_UPLOAD_PATHS)


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
            if is_multipart:
                limit = settings.max_request_body_bytes
            elif _is_image_upload_path(request.url.path):
                # A base64 image in a JSON body is well over the 1 MB JSON cap; the
                # route enforces the real per-image 10 MB limit on the decoded bytes.
                limit = settings.max_upload_body_bytes
            else:
                limit = settings.max_json_body_bytes
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
