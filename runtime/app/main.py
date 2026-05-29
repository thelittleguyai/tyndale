"""FastAPI application entry point (Phase 1C skeleton)."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.config import get_settings
from app.hooks import log_stub_warnings
from app.middleware.cors import add_cors
from app.middleware.error_handler import add_error_handlers
from app.middleware.request_logger import RequestLoggerMiddleware
from app.routes import audit, cases, coverage, dashboard, feedback, health, upload

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.warn_missing_in_prod()
    log_stub_warnings()
    log.info("runtime.startup", node_env=settings.node_env, version="0.1.0")
    yield
    log.info("runtime.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Tyndale Runtime", version="0.1.0", lifespan=lifespan)
    add_cors(app, settings)
    app.add_middleware(RequestLoggerMiddleware)
    add_error_handlers(app)
    app.include_router(health.router)
    app.include_router(upload.router, prefix="/v1")
    app.include_router(audit.router, prefix="/v1")
    app.include_router(feedback.router, prefix="/v1")
    app.include_router(dashboard.router, prefix="/v1")
    app.include_router(cases.router, prefix="/v1")
    app.include_router(coverage.router, prefix="/v1")
    return app


app = create_app()
