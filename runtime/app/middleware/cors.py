"""CORS — explicit allow-list, never wildcard (Phase 2K.2 / DL-46).

allow_credentials=True is incompatible with a wildcard origin, and the runtime
is public, so origins are an EXPLICIT list from CORS_ALLOWED_ORIGINS (prod:
https://dev.tyndaleapp.net + https://app.tyndaleapp.net). In development we also
allow the local marketing (:3000) + Expo web (:8081) origins. Methods + headers
are explicit, not "*".
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

log = structlog.get_logger(__name__)

_DEV_ORIGINS = ("http://localhost:3000", "http://localhost:8081")
_ALLOW_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
_ALLOW_HEADERS = ["Authorization", "Content-Type", "X-Request-ID", "X-Requested-With"]


def add_cors(app: FastAPI, settings: Settings) -> None:
    origins = [o for o in settings.cors_origins if o != "*"]  # never wildcard with credentials
    if "*" in settings.cors_origins:
        log.warning("cors.wildcard_rejected", node_env=settings.node_env)
    if settings.node_env == "development":
        for dev_origin in _DEV_ORIGINS:
            if dev_origin not in origins:
                origins.append(dev_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=_ALLOW_METHODS,
        allow_headers=_ALLOW_HEADERS,
    )
