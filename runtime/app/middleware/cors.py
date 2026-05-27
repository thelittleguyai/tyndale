"""CORS configuration from the env allow-list. Wildcard rejected outside dev."""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

log = structlog.get_logger(__name__)


def add_cors(app: FastAPI, settings: Settings) -> None:
    origins = settings.cors_origins
    if "*" in origins and not settings.node_env == "development":
        log.warning("cors.wildcard_rejected_outside_dev", node_env=settings.node_env)
        origins = [o for o in origins if o != "*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
