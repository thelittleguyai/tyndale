"""CO-17 — /v1/profile routes (18+ gate, terms -> consent_history, completion flip)."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.auth.dev_user import DEV_USER_ID
from app.db.base import AsyncSessionLocal
from app.db.models.consent_history import ConsentHistory
from app.db.models.users import User


async def _reset_dev_user() -> None:
    """The dev user is shared across the persistent test DB — reset the profile
    fields so each test is deterministic regardless of order / prior runs."""
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(User)
            .where(User.user_id == DEV_USER_ID)
            .values(
                first_name=None,
                last_name=None,
                date_of_birth=None,
                service_consent=False,
                profile_completed=False,
                profile_completed_at=None,
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_profile_state_initially_incomplete(client: AsyncClient):
    await _reset_dev_user()
    r = await client.get("/v1/profile/state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile_completed"] is False
    assert body["email"]
    assert "has_insurance_card" in body


@pytest.mark.asyncio
async def test_patch_rejects_underage_dob(client: AsyncClient):
    await _reset_dev_user()
    underage = date(date.today().year - 10, 6, 15).isoformat()
    r = await client.patch("/v1/profile", json={"date_of_birth": underage})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_future_dob(client: AsyncClient):
    await _reset_dev_user()
    future = date(date.today().year + 1, 6, 15).isoformat()
    r = await client.patch("/v1/profile", json={"date_of_birth": future})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_completes_profile_and_writes_consent_history(client: AsyncClient):
    await _reset_dev_user()
    async with AsyncSessionLocal() as s:
        before = (
            await s.execute(
                select(func.count())
                .select_from(ConsentHistory)
                .where(ConsentHistory.user_id == DEV_USER_ID)
            )
        ).scalar_one()

    dob = date(date.today().year - 30, 6, 15).isoformat()
    r = await client.patch(
        "/v1/profile",
        json={"first_name": "Jane", "last_name": "Doe", "date_of_birth": dob, "accept_terms": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile_completed"] is True
    assert body["first_name"] == "Jane"

    async with AsyncSessionLocal() as s:
        after = (
            await s.execute(
                select(func.count())
                .select_from(ConsentHistory)
                .where(ConsentHistory.user_id == DEV_USER_ID)
            )
        ).scalar_one()
        u = (await s.execute(select(User).where(User.user_id == DEV_USER_ID))).scalar_one()
    assert after == before + 1  # one terms-acceptance audit row
    assert u.service_consent is True
    assert u.profile_completed_at is not None


@pytest.mark.asyncio
async def test_patch_incomplete_does_not_flip(client: AsyncClient):
    await _reset_dev_user()
    # name only, no DOB / terms -> still incomplete
    r = await client.patch("/v1/profile", json={"first_name": "Jane"})
    assert r.status_code == 200, r.text
    assert r.json()["profile_completed"] is False
