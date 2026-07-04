"""Account deletion (Phase 2.4): BlobStorage.delete, the shared scrub (identity + insurance
rows + card-image blobs + jwt_version bump), and the member-facing self-service delete route."""

from __future__ import annotations

import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.insurance_info import InsuranceInfo
from app.db.models.users import User
from app.ingestion.blob_storage import BlobStorage
from app.main import app
from app.services.account_deletion import scrub_user_account


def _force_local_blob(monkeypatch, tmp_path) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "azure_storage_connection_string", None)  # force the local-FS backend
    monkeypatch.setattr(s, "bulk_local_dir", str(tmp_path))


async def _make_user_with_pii(blob_ref: str | None = None) -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        u = User(
            email=f"del{uuid.uuid4().hex[:10]}@example.com",
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
                blob_ref=blob_ref or f"insurance-cards/{u.user_id}/front.jpg",
            )
        )
        await s.commit()
        return u.user_id


async def _get_user(uid: uuid.UUID) -> User:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(User).where(User.user_id == uid))).scalar_one()


@pytest.mark.asyncio
async def test_blob_storage_delete_local(monkeypatch, tmp_path):
    _force_local_blob(monkeypatch, tmp_path)
    store = BlobStorage(container="uploads")
    await store.write_bytes("insurance-cards/x/front.jpg", b"img")
    assert await store.exists("insurance-cards/x/front.jpg")
    assert await store.delete("insurance-cards/x/front.jpg") is True
    assert not await store.exists("insurance-cards/x/front.jpg")
    assert await store.delete("insurance-cards/x/front.jpg") is False  # idempotent


@pytest.mark.asyncio
async def test_scrub_deletes_pii_rows_and_card_blob(monkeypatch, tmp_path):
    _force_local_blob(monkeypatch, tmp_path)
    blob_ref = "insurance-cards/scrubme/front.jpg"
    await BlobStorage(container="uploads").write_bytes(blob_ref, b"cardimg")
    uid = await _make_user_with_pii(blob_ref=blob_ref)

    async with AsyncSessionLocal() as s:
        u = (await s.execute(select(User).where(User.user_id == uid))).scalar_one()
        report = await scrub_user_account(u, s)
        await s.commit()

    scrubbed = await _get_user(uid)
    assert scrubbed.first_name is None
    assert scrubbed.last_name is None
    assert scrubbed.date_of_birth is None
    assert scrubbed.phone is None
    assert scrubbed.email.startswith("deleted-")
    assert scrubbed.email.endswith("@deleted.tyndaleapp.net")
    assert scrubbed.soft_deleted_at is not None
    assert (scrubbed.jwt_version or 0) >= 2  # bumped from the default 1

    async with AsyncSessionLocal() as s:
        info = (
            (await s.execute(select(InsuranceInfo).where(InsuranceInfo.user_id == uid)))
            .scalars()
            .all()
        )
        cards = (
            (await s.execute(select(InsuranceCard).where(InsuranceCard.user_id == uid)))
            .scalars()
            .all()
        )
    assert info == []
    assert cards == []
    assert report["insurance_card_blobs_deleted"] == 1
    assert not await BlobStorage(container="uploads").exists(blob_ref)


@pytest.mark.asyncio
async def test_self_delete_route_scrubs_and_signs_out(client: AsyncClient, monkeypatch, tmp_path):
    _force_local_blob(monkeypatch, tmp_path)
    uid = await _make_user_with_pii()
    fresh = await _get_user(uid)

    def _as_fresh_user() -> CurrentUser:
        return CurrentUser(user_id=uid, email=fresh.email, first_name="Jane", user_type="user")

    app.dependency_overrides[current_user] = _as_fresh_user
    try:
        r = await client.post("/v1/user/me/delete-request")
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert r.status_code == 200
    assert r.json()["status"] == "deleted"

    scrubbed = await _get_user(uid)
    assert scrubbed.soft_deleted_at is not None
    assert scrubbed.soft_deleted_by == uid  # self-initiated
    assert scrubbed.first_name is None
    assert scrubbed.email.startswith("deleted-")
