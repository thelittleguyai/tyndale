"""FastAPI application entry point (Phase 1C skeleton)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.config import get_settings
from app.hooks import log_stub_warnings
from app.middleware.admin_ip_allowlist import AdminIPAllowlistMiddleware
from app.middleware.cors import add_cors
from app.middleware.error_handler import add_error_handlers
from app.middleware.phi_log_filter import PHILogFilter, scrub_event
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.request_size import RequestSizeLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import (
    admin,
    audit,
    auth,
    cases,
    coverage,
    dashboard,
    encounter,
    feedback,
    health,
    intake,
    upload,
    user,
)

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        scrub_event,  # PHI scrub bridge before render/ship (Phase 2K.2 / DL-46)
        structlog.dev.ConsoleRenderer(),
    ]
)

# Best-effort PHI scrub on stdlib loggers too (uvicorn access logs, etc.).
logging.getLogger().addFilter(PHILogFilter())

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
    # Starlette's add_middleware PREPENDS — the LAST added is the OUTERMOST. We
    # want, outer→inner: RequestLogger → CORS → SecurityHeaders → RequestSize →
    # RateLimit → AdminIPAllowlist → routes. So add them inner-first. This puts
    # the security-header + CORS + request-id stamps OUTSIDE the 413/429 short-
    # circuits, so a rejected request still gets those headers.
    app.add_middleware(AdminIPAllowlistMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
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
    app.include_router(encounter.router, prefix="/v1")
    app.include_router(user.router, prefix="/v1")
    app.include_router(auth.router, prefix="/v1")
    app.include_router(intake.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    return app


app = create_app()
