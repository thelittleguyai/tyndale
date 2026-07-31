"""Deletion / access-request INTAKE STUB (Brock §A2 state 5 / script §12).

SCOPE — deliberately narrow. This accepts a request and confirms receipt. It does NOT look
anything up, and it discloses NOTHING: the patient-in-document lookup + fulfillment is D2
work with Jonas. The stub exists so a statutory right has an intake path at all, instead of
none.

Unauthenticated by design: the person exercising the right may not have (or may be asking to
delete) an account. That means the endpoint must never confirm or deny that a person, case,
or record exists — the receipt is identical in every case.
"""

from __future__ import annotations

import datetime

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_loader import orchestration_step
from app.db.session import get_session
from app.schemas.access_request import AccessRequestIn, AccessRequestResult
from app.security.audit_writer import build_audit_event

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


@router.post("/access-request", response_model=AccessRequestResult)
async def submit_access_request(
    body: AccessRequestIn,
    session: AsyncSession = Depends(get_session),
) -> AccessRequestResult:
    """Record an access/deletion request and confirm receipt. No lookup, no disclosure."""
    session.add(
        build_audit_event(
            event_type="access_request",
            actor="public",  # unauthenticated intake — no user id to attribute
            payload={
                "request_type": body.request_type,
                "patient_name": body.patient_name,
                "contact": body.contact,
                "relationship": body.relationship,
                "details": body.details,
                "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            outcome="success",
        )
    )
    await session.commit()
    # PHI-free log line. NOTE: no analytics row is written here — analytics_events.user_id is
    # NOT NULL (FK to users) and this intake is deliberately unauthenticated, so an anonymous
    # event has nowhere to land today. `access_request_received` is REGISTERED (name + schema
    # frozen, not_yet_live) and starts emitting when analytics grows an anonymous path; until
    # then the encrypted audit row above is the record of receipt.
    log.info("access_request.received", request_type=body.request_type)
    return AccessRequestResult(received=True, message=orchestration_step("access_request.received"))


@router.get("/access-request", response_model=AccessRequestResult)
async def access_request_intro() -> AccessRequestResult:
    """The settings-surface copy explaining the request path (what it does, what it doesn't)."""
    return AccessRequestResult(received=False, message=orchestration_step("access_request.intro"))
