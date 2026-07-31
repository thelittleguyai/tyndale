"""Attest-and-proceed endpoints (Brock July 16 §A2 state 1 — COMPLIANCE).

POST /v1/case/{id}/attest          — record the relationship attestation, unblock the flow
POST /v1/case/{id}/attest/decline  — "I'm not authorized": close the case gracefully, no audit

Both persist an ``attestation`` audit event through the ENCRYPTED envelope (build_audit_event) —
that persistence is the compliance point, and the decline is logged exactly like the attestation.
The audit payload carries the patient name AS EXTRACTED (protected by the envelope); the
analytics event carries only the relationship enum (PHI-free by construction, Rule 2).
"""

from __future__ import annotations

import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.attest import RELATIONSHIPS, attest_edge_signals
from app.agents.context_loader import orchestration_step
from app.analytics.emit import emit
from app.auth import CurrentUser, current_user
from app.db.session import get_session
from app.routes.case_access import require_case_owner
from app.schemas.attest import AttestRequest, AttestResult
from app.security.audit_writer import build_audit_event

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

_EDGE_KEY = {"teen": "attest.edge_teen", "deceased": "attest.edge_deceased",
             "substance": "attest.edge_substance"}


async def _record(
    session: AsyncSession,
    case,
    user: CurrentUser,
    *,
    action: str,
    relationship: str | None,
    patient_deceased: bool = False,
) -> None:
    """One attestation audit row (encrypted envelope) + its PHI-free analytics event."""
    session.add(
        build_audit_event(
            event_type="attestation",
            actor=str(user.user_id),
            user_id=user.user_id,
            case_file_id=case.case_file_id,
            payload={
                # D2 attest-spine event shape — exactly §3's named fields, nothing invented.
                "action": action,  # attested | declined
                "relationship": relationship,
                "patient_name_as_extracted": case.patient_name,
                "patient_deceased": patient_deceased,
                "attested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            outcome="success",
        )
    )
    await emit(
        "attestation_recorded" if action == "attested" else "attestation_declined",
        user_id=user.user_id,
        case_file_id=case.case_file_id,
        properties={"relationship": relationship} if relationship else None,
    )


@router.post("/case/{case_file_id}/attest", response_model=AttestResult)
async def attest(
    case_file_id: str,
    body: AttestRequest,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AttestResult:
    case = await require_case_owner(case_file_id, user, session)
    if body.relationship not in RELATIONSHIPS:
        raise HTTPException(status_code=422, detail=f"relationship must be one of {RELATIONSHIPS}")
    if case.attest_status == "declined":
        raise HTTPException(status_code=409, detail="case was closed by an authorization decline")

    case.attest_status = "attested"
    await _record(
        session, case, user,
        action="attested", relationship=body.relationship, patient_deceased=body.patient_deceased,
    )
    signals = attest_edge_signals(case, patient_deceased=body.patient_deceased)
    await session.commit()

    # Re-render the thread now that the gate is open (verification cards were held behind it).
    from app.agents import thread_bridge

    if thread_bridge.enabled():
        await thread_bridge.bridge_case_state(case_file_id)

    return AttestResult(
        case_file_id=case_file_id,
        attest_status="attested",
        case_status=case.status,
        confirmation=orchestration_step("attest.confirm"),
        edge_prompts=[orchestration_step(_EDGE_KEY[s]) for s in signals],
    )


@router.post("/case/{case_file_id}/attest/decline", response_model=AttestResult)
async def attest_decline(
    case_file_id: str,
    user: CurrentUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AttestResult:
    """"I'm not authorized" — close the flow gracefully: no audit runs, an honest message, and
    the decline is logged like any attestation (the compliance record covers both directions)."""
    case = await require_case_owner(case_file_id, user, session)
    case.attest_status = "declined"
    case.status = "attest_declined"
    await _record(session, case, user, action="declined", relationship=None)
    await session.commit()

    from app.agents import thread_bridge

    if thread_bridge.enabled():
        await thread_bridge.bridge_case_state(case_file_id)

    return AttestResult(
        case_file_id=case_file_id,
        attest_status="declined",
        case_status="attest_declined",
        confirmation=orchestration_step("attest.decline_ack"),
    )
