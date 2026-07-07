"""CO-17 — /v1/insurance routes (card upload to Blob, extraction, signed image)."""

from __future__ import annotations

import base64
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.auth.dev_user import DEV_USER_ID
from app.db.base import AsyncSessionLocal
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.insurance_info import InsuranceInfo
from app.db.models.users import User

_IMG_BYTES = b"\x89PNG\r\n\x1a\nfake-card-image-bytes"
_IMG_B64 = base64.b64encode(_IMG_BYTES).decode()


async def _reset_dev_insurance() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(delete(InsuranceCard).where(InsuranceCard.user_id == DEV_USER_ID))
        await s.execute(delete(InsuranceInfo).where(InsuranceInfo.user_id == DEV_USER_ID))
        await s.commit()


def _upload(card_type: str = "front", mime: str = "image/png") -> dict:
    return {"card_type": card_type, "image_base64": _IMG_B64, "mime_type": mime}


@pytest.fixture(autouse=True)
def _stub_card_ocr(monkeypatch):
    """CO-17 card routes are validated against the deterministic card STUB. Force stub mode so
    the ambient dev .env.local (USE_REAL_OCR=true pointed at a placeholder DI endpoint) doesn't
    turn every extraction into a degraded/empty projection. The real-OCR degradation path — no
    fabricated card when DI is unavailable — is locked in
    test_upload_ocr_and_cors.test_run_insurance_card_ocr_degrades_under_real_ocr."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "use_real_ocr", False)


@pytest.mark.asyncio
async def test_card_upload_stores_blob_not_base64_and_extracts(client: AsyncClient):
    await _reset_dev_insurance()
    r = await client.post("/v1/insurance/card/upload", json=_upload("front"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["card_type"] == "front"
    assert body["extraction_status"] in ("extracted", "unreadable", "error")
    assert body["insurance_info"]["insurer"] == "Blue Shield PPO"  # stub front mapping
    assert body["insurance_info"]["has_front"] is True

    # The card row stores a blob_ref PATH — NOT base64 image data.
    async with AsyncSessionLocal() as s:
        card = (
            await s.execute(
                select(InsuranceCard).where(
                    InsuranceCard.user_id == DEV_USER_ID, InsuranceCard.card_type == "front"
                )
            )
        ).scalar_one()
    assert card.blob_ref.startswith("insurance-cards/")
    assert _IMG_B64 not in card.blob_ref
    assert card.file_size == len(_IMG_BYTES)


@pytest.mark.asyncio
async def test_card_upload_replaces_same_side(client: AsyncClient):
    await _reset_dev_insurance()
    await client.post("/v1/insurance/card/upload", json=_upload("front"))
    await client.post("/v1/insurance/card/upload", json=_upload("front"))
    async with AsyncSessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(InsuranceCard).where(
                        InsuranceCard.user_id == DEV_USER_ID, InsuranceCard.card_type == "front"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1  # UNIQUE(user_id, card_type) — replaced, not duplicated


@pytest.mark.asyncio
async def test_card_upload_validation(client: AsyncClient):
    await _reset_dev_insurance()
    assert (await client.post("/v1/insurance/card/upload", json=_upload("side"))).status_code == 422
    bad_mime = await client.post(
        "/v1/insurance/card/upload", json=_upload("front", "application/pdf")
    )
    assert bad_mime.status_code == 422


@pytest.mark.asyncio
async def test_unreadable_card_is_soft_not_500(client: AsyncClient, monkeypatch):
    await _reset_dev_insurance()

    async def _boom(_bytes):
        raise RuntimeError("DI exploded")

    monkeypatch.setattr("app.routes.insurance.run_insurance_card_ocr", _boom)
    r = await client.post("/v1/insurance/card/upload", json=_upload("front"))
    assert r.status_code == 200, r.text  # never a 500 on a bad card
    assert r.json()["extraction_status"] == "error"


@pytest.mark.asyncio
async def test_two_sides_merge(client: AsyncClient):
    await _reset_dev_insurance()
    await client.post("/v1/insurance/card/upload", json=_upload("front"))
    r = await client.post("/v1/insurance/card/upload", json=_upload("back"))
    body = r.json()
    assert body["insurance_info"]["has_front"] is True
    assert body["insurance_info"]["has_back"] is True
    assert body["insurance_info"]["extraction_status"] == "merged"
    info = (await client.get("/v1/insurance/info")).json()
    assert info["insurer"] == "Blue Shield PPO"


@pytest.mark.asyncio
async def test_card_image_streams_phi_free(client: AsyncClient):
    await _reset_dev_insurance()
    await client.post("/v1/insurance/card/upload", json=_upload("front"))
    r = await client.get("/v1/insurance/card/front/image")
    assert r.status_code == 200, r.text
    assert r.content == _IMG_BYTES  # local mode streams the stored bytes
    url = str(r.url)
    assert "/v1/insurance/card/front/image" in url
    assert "member" not in url.lower()  # PHI-free path


@pytest.mark.asyncio
async def test_card_image_404_missing_and_other_user(client: AsyncClient):
    await _reset_dev_insurance()
    # The dev user has no card -> 404.
    assert (await client.get("/v1/insurance/card/back/image")).status_code == 404

    # Another user's card is NOT visible to the dev user.
    other = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add(User(user_id=other, email=f"other-{other.hex[:8]}@example.com"))
        await s.flush()  # user must exist before the card's FK insert (no relationship())
        s.add(
            InsuranceCard(
                user_id=other,
                card_type="back",
                blob_ref="insurance-cards/x/back",
                mime_type="image/png",
            )
        )
        await s.commit()
    assert (await client.get("/v1/insurance/card/back/image")).status_code == 404
