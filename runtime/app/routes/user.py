"""User + improvement-consent routes (Phase 2J).

- GET    /v1/user/me                 — current user profile
- PATCH  /v1/user/me                 — flip improvement_consent (immediate)
- GET    /v1/user/me/consent-history — audit trail of consent changes

Consent flip semantics (L05/L06):
  false -> true: retroactively enqueue all this user's prior feedback_events
                 (not already queued) for the de-id pipeline.
  true  -> false: remove this user's still-pending events from the triage
                 queue, but DO NOT touch feedback_deid_candidates — already-
                 de-identified data is no longer personal and stays.
The dev-mode current_user stub backs this until Phase 2K swaps in real auth.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.consent_history import ConsentHistory
from app.db.models.feedback import FeedbackEvent, FeedbackTriageQueue
from app.db.models.users import User
from app.db.session import get_session
from app.routes.auth import _clear_session_cookie
from app.security.audit_writer import build_audit_event
from app.services.account_deletion import scrub_user_account
from app.schemas.feedback import (
    ConsentHistoryEntry,
    ConsentHistoryPayload,
    ConsentUpdate,
    UserProfile,
)
import structlog

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


async def _load_user(session: AsyncSession, user_id) -> User:
    return (await session.execute(select(User).where(User.user_id == user_id))).scalar_one()


def _profile(u: User, first_name: str) -> UserProfile:
    return UserProfile(
        id=str(u.user_id),
        first_name=first_name,
        email=u.email,
        user_type=u.user_type,
        improvement_consent=bool(u.improvement_consent),
        created_at=u.created_at.isoformat() if u.created_at else "",
    )


@router.get("/user/me", response_model=UserProfile)
async def get_me(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> UserProfile:
    u = await _load_user(session, user.user_id)
    return _profile(u, user.first_name)


@router.patch("/user/me", response_model=UserProfile)
async def patch_me(
    body: ConsentUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> UserProfile:
    u = await _load_user(session, user.user_id)
    old = bool(u.improvement_consent)
    new = bool(body.improvement_consent)

    if old != new:
        u.improvement_consent = new
        session.add(ConsentHistory(user_id=u.user_id, from_consent=old, to_consent=new))

        if new:
            # Retroactive opt-in: enqueue this user's prior events that aren't
            # already queued. (Idempotent — skip events with an existing queue row.)
            event_ids = (await session.execute(
                select(FeedbackEvent.id).where(FeedbackEvent.user_id == u.user_id)
            )).scalars().all()
            already = set((await session.execute(
                select(FeedbackTriageQueue.feedback_event_id)
                .where(FeedbackTriageQueue.feedback_event_id.in_(event_ids))
            )).scalars().all()) if event_ids else set()
            enqueued = 0
            for eid in event_ids:
                if eid in already:
                    continue
                session.add(FeedbackTriageQueue(feedback_event_id=eid))
                enqueued += 1
            # Flip the stored consent flag on those events for consistency.
            if event_ids:
                await session.execute(
                    update(FeedbackEvent)
                    .where(FeedbackEvent.user_id == u.user_id)
                    .values(improvement_consent=True)
                )
            log.info("consent.retroactive_enqueue", user_id=str(u.user_id), enqueued=enqueued)
        else:
            # Opt-out: drop still-pending queue rows for this user's events.
            # feedback_deid_candidates are intentionally left untouched (L05 rule 2).
            user_event_ids = (await session.execute(
                select(FeedbackEvent.id).where(FeedbackEvent.user_id == u.user_id)
            )).scalars().all()
            if user_event_ids:
                await session.execute(
                    delete(FeedbackTriageQueue)
                    .where(FeedbackTriageQueue.feedback_event_id.in_(user_event_ids))
                    .where(FeedbackTriageQueue.status == "queued")
                )
                await session.execute(
                    update(FeedbackEvent)
                    .where(FeedbackEvent.user_id == u.user_id)
                    .values(improvement_consent=False)
                )
            log.info("consent.opt_out_dequeue", user_id=str(u.user_id))

        await session.commit()

    u = await _load_user(session, user.user_id)
    return _profile(u, user.first_name)


@router.get("/user/me/consent-history", response_model=ConsentHistoryPayload)
async def get_consent_history(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ConsentHistoryPayload:
    rows = (await session.execute(
        select(ConsentHistory)
        .where(ConsentHistory.user_id == user.user_id)
        .order_by(ConsentHistory.changed_at.asc())
    )).scalars().all()
    return ConsentHistoryPayload(
        user_id=str(user.user_id),
        history=[
            ConsentHistoryEntry(
                changed_at=r.changed_at.isoformat() if r.changed_at else "",
                from_consent=r.from_consent,
                to_consent=r.to_consent,
            )
            for r in rows
        ],
    )


@router.post("/user/me/delete-request")
async def request_account_deletion(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    """Self-service account deletion (Phase 2.4). Runs the SAME PHI scrub as the admin
    soft-delete (identity anonymized, insurance rows + card-image blobs deleted, jwt_version
    bumped to invalidate sessions), records a user_action audit row, and clears the session
    cookie so the caller is signed out. Idempotent — a re-request on an already-deleted account
    is a no-op. user_id / case files / audit trail are retained (HIPAA)."""
    row = (
        await session.execute(select(User).where(User.user_id == user.user_id))
    ).scalar_one_or_none()
    if row is not None and row.soft_deleted_at is None:
        report = await scrub_user_account(row, session)
        row.soft_deleted_by = row.user_id  # self-initiated
        row.updated_at = datetime.now(timezone.utc)
        session.add(
            build_audit_event(
                event_type="user_action",
                actor=str(row.user_id),
                user_id=row.user_id,
                payload={"action": "self_delete", "initiated_by": "self", **report},
                outcome="success",
            )
        )
        await session.commit()
        log.info("account.self_delete", user_id=str(row.user_id))

    resp = JSONResponse({"ok": True, "status": "deleted"})
    _clear_session_cookie(resp)  # sign out; the jwt_version bump also invalidates the token
    return resp
