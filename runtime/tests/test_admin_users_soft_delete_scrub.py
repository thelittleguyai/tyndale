"""CO-17 soft-delete PHI scrub (security spine).

Extends the existing admin soft-delete: after a soft-delete, ALL identity data is
scrubbed — user identity fields nulled + email anonymized, and the associated
insurance_info + insurance_cards rows are deleted. user_id + audit trail persist.

Style mirrors tests/test_admin_users.py (dev user is admin → `client` is admin;
targets created directly via AsyncSessionLocal).
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.insurance_info import InsuranceInfo
from app.db.models.users import User


async def _make_user_with_pii() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        u = User(
            email=f"scrub{uuid.uuid4().hex[:10]}@example.com",
            phone="+15551234567",
            first_name="Jane",
            last_name="Patient",
            date_of_birth=datetime.date(1990, 4, 1),
        )
        s.add(u)
        await s.flush()
        s.add(
            InsuranceInfo(
                user_id=u.user_id,
                insurer="Anthem",
                member_id="ABC123456789",
                member_name="Jane Patient",
                member_birth_date=datetime.date(1990, 4, 1),
            )
        )
        s.add(
            InsuranceCard(
                user_id=u.user_id,
                card_type="front",
                blob_ref=f"insurance-cards/{u.user_id}/front.jpg",
            )
        )
        await s.commit()
        return u.user_id


async def _get_user(uid: uuid.UUID) -> User:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(User).where(User.user_id == uid))).scalar_one()


async def _insurance_counts(uid: uuid.UUID) -> tuple[int, int]:
    async with AsyncSessionLocal() as s:
        info = (
            await s.execute(select(InsuranceInfo).where(InsuranceInfo.user_id == uid))
        ).scalars().all()
        cards = (
            await s.execute(select(InsuranceCard).where(InsuranceCard.user_id == uid))
        ).scalars().all()
        return len(info), len(cards)


@pytest.mark.asyncio
async def test_soft_delete_scrubs_all_identity_and_insurance(client: AsyncClient):
    uid = await _make_user_with_pii()

    r = await client.post(f"/v1/admin/users/{uid}/soft-delete")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "soft_deleted"
    assert body["scrubbed"]["insurance_info_rows_deleted"] == 1
    assert body["scrubbed"]["insurance_card_rows_deleted"] == 1

    u = await _get_user(uid)
    # Identity fields nulled.
    assert u.first_name is None
    assert u.last_name is None
    assert u.date_of_birth is None
    assert u.phone is None
    # Email anonymized (pattern preserved), user_id + soft-delete metadata kept.
    assert u.email.startswith("deleted-") and u.email.endswith("@deleted.tyndaleapp.net")
    assert u.soft_deleted_at is not None

    # Insurance rows gone.
    info_n, cards_n = await _insurance_counts(uid)
    assert info_n == 0
    assert cards_n == 0


@pytest.mark.asyncio
async def test_soft_delete_is_idempotent(client: AsyncClient):
    uid = await _make_user_with_pii()
    r1 = await client.post(f"/v1/admin/users/{uid}/soft-delete")
    assert r1.status_code == 200
    r2 = await client.post(f"/v1/admin/users/{uid}/soft-delete")
    assert r2.status_code == 200
    assert r2.json()["status"] == "soft_deleted"
