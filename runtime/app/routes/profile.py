"""User profile routes (CO-17).

- GET   /v1/profile/state — what the onboarding gate + settings read.
- PATCH /v1/profile       — name / DOB / phone / terms acceptance.

DOB is gated 18+ (DL-17): a future date or an age < 18 is a 422. Accepting terms
sets service_consent=true and writes a consent_history audit row (DL-? terms trail).
When name + DOB + terms are all present, profile_completed flips true (+ timestamp),
which the post-auth router uses to send the user to onboarding exactly once. Own row
only (current_user).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.consent_history import ConsentHistory
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.users import User
from app.db.session import get_session
from app.schemas.profile import ProfilePatch, ProfileState

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

MIN_AGE_YEARS = 18


def _age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


async def _has_card(session: AsyncSession, user_id) -> bool:
    n = (
        await session.execute(
            select(func.count()).select_from(InsuranceCard).where(InsuranceCard.user_id == user_id)
        )
    ).scalar_one()
    return bool(n)


async def _state(session: AsyncSession, user_id) -> ProfileState:
    u = (await session.execute(select(User).where(User.user_id == user_id))).scalar_one()
    return ProfileState(
        first_name=u.first_name,
        last_name=u.last_name,
        date_of_birth=u.date_of_birth,
        phone=u.phone,
        email=u.email,
        profile_completed=bool(u.profile_completed),
        has_insurance_card=await _has_card(session, user_id),
    )


@router.get("/profile/state", response_model=ProfileState)
async def get_profile_state(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ProfileState:
    return await _state(session, user.user_id)


@router.patch("/profile", response_model=ProfileState)
async def patch_profile(
    body: ProfilePatch,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ProfileState:
    u = (await session.execute(select(User).where(User.user_id == user.user_id))).scalar_one()

    if body.date_of_birth is not None:
        today = datetime.now(timezone.utc).date()
        if body.date_of_birth > today:
            raise HTTPException(status_code=422, detail="Date of birth cannot be in the future.")
        if _age_on(body.date_of_birth, today) < MIN_AGE_YEARS:
            raise HTTPException(status_code=422, detail="You must be at least 18 to use Tyndale.")
        u.date_of_birth = body.date_of_birth

    if body.first_name is not None:
        u.first_name = body.first_name.strip() or None
    if body.last_name is not None:
        u.last_name = body.last_name.strip() or None
    if body.phone is not None:
        u.phone = body.phone.strip() or None

    if body.accept_terms and not u.service_consent:
        session.add(
            ConsentHistory(user_id=u.user_id, from_consent=bool(u.service_consent), to_consent=True)
        )
        u.service_consent = True

    # Gate: required fields are name + DOB + terms. Flip once.
    if (
        u.first_name
        and u.last_name
        and u.date_of_birth
        and u.service_consent
        and not u.profile_completed
    ):
        u.profile_completed = True
        u.profile_completed_at = datetime.now(timezone.utc)

    await session.commit()
    return await _state(session, user.user_id)
