"""Admin console router (Phase CO-6A + CO-9).

Assembles every admin sub-router under one APIRouter, included by main.py at /v1. DL-60:
every route requires admin; a non-admin gets 404 (the console's existence is never
revealed). CO-9 modules are appended here as they land.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.routes.admin import audit, cases, crons, knowledge_gaps, qdrant, system, users
from app.routes.admin._deps import admin_user, audit_admin_action

router = APIRouter()
router.include_router(cases.router)
router.include_router(users.router)
router.include_router(qdrant.router)
router.include_router(audit.router)
router.include_router(system.router)
router.include_router(crons.router)
router.include_router(knowledge_gaps.router)

__all__ = ["router", "admin_user", "audit_admin_action"]
