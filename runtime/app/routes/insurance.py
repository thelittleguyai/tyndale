"""Insurance routes (CO-17).

- POST /v1/insurance/card/upload — store the card IMAGE in Blob (never base64 in
  Postgres), extract via Azure healthInsuranceCard, merge with the other side, upsert
  insurance_info. NEVER 500 on a bad card — a soft extraction_status instead.
- GET  /v1/insurance/info        — the merged insurance_info (subset).
- GET  /v1/insurance/card/{type}/image — a 15-min signed Blob URL on Azure (302), or
  the bytes streamed through the authed route locally. PHI-free URL either way.

Own data only (current_user). member_id / DOB / names / raw JSON never hit logs or URLs.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.insurance_info import InsuranceInfo
from app.db.session import get_session
from app.ingestion.blob_storage import BlobStorage
from app.schemas.profile import CardUploadRequest, CardUploadResult, InsuranceInfoOut
from app.sources.case_data import parse_iso_date
from app.sources.insurance_card import (
    DATE_FIELDS,
    map_card_result,
    merge_card_sides,
    run_insurance_card_ocr,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)

_MAX_CARD_BYTES = 10 * 1024 * 1024
_ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/heic", "image/webp"}
_CARD_TYPES = ("front", "back")


def _card_storage() -> BlobStorage:
    # Card images go to the uploads container (not the bulk-data container).
    return BlobStorage(container=get_settings().azure_storage_uploads_container)


def _blob_path(user_id, card_type: str) -> str:
    # PHI-free key: user id + side, no member data.
    return f"insurance-cards/{user_id}/{card_type}"


async def _sides_present(session: AsyncSession, user_id) -> tuple[bool, bool]:
    rows = (
        (
            await session.execute(
                select(InsuranceCard.card_type).where(InsuranceCard.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    return ("front" in rows, "back" in rows)


def _info_out(info: InsuranceInfo | None, has_front: bool, has_back: bool) -> InsuranceInfoOut:
    if info is None:
        return InsuranceInfoOut(has_front=has_front, has_back=has_back)
    return InsuranceInfoOut(
        insurer=info.insurer,
        plan_name=info.plan_name,
        plan_type=info.plan_type,
        member_id=info.member_id,
        group_number=info.group_number,
        member_name=info.member_name,
        effective_date=info.effective_date,
        rx_bin=info.rx_bin,
        rx_pcn=info.rx_pcn,
        copays=info.copays,
        extraction_status=info.extraction_status,
        has_front=has_front,
        has_back=has_back,
    )


@router.post("/insurance/card/upload", response_model=CardUploadResult)
async def upload_card(
    body: CardUploadRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> CardUploadResult:
    if body.card_type not in _CARD_TYPES:
        raise HTTPException(status_code=422, detail="card_type must be 'front' or 'back'")
    if body.mime_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="Unsupported image type.")
    try:
        image = base64.b64decode(body.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="image is not valid base64")
    if not image:
        raise HTTPException(status_code=422, detail="empty image")
    if len(image) > _MAX_CARD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10MB limit.")

    # 1) Store the IMAGE in Blob — never base64 in Postgres.
    blob_ref = _blob_path(user.user_id, body.card_type)
    await _card_storage().write_bytes(blob_ref, image)

    # 2) Extract — a bad scan is a soft failure, never a 500.
    try:
        projected = await run_insurance_card_ocr(image)
        extraction_status = "extracted" if projected.get("fields") else "unreadable"
    except Exception as exc:  # noqa: BLE001
        log.warning("insurance.card_ocr_failed", card_type=body.card_type, error=str(exc))
        projected = {"fields": {}}
        extraction_status = "error"

    # 3) Upsert the card row (UNIQUE(user_id, card_type) → re-upload replaces the side).
    card = (
        await session.execute(
            select(InsuranceCard).where(
                InsuranceCard.user_id == user.user_id,
                InsuranceCard.card_type == body.card_type,
            )
        )
    ).scalar_one_or_none()
    if card is None:
        card = InsuranceCard(user_id=user.user_id, card_type=body.card_type)
        session.add(card)
    card.blob_ref = blob_ref
    card.mime_type = body.mime_type
    card.file_size = len(image)
    card.raw_ocr_json = projected
    card.extraction_status = extraction_status

    # 4) Merge with the other side's stored projection, then upsert insurance_info.
    other_type = "back" if body.card_type == "front" else "front"
    other = (
        await session.execute(
            select(InsuranceCard).where(
                InsuranceCard.user_id == user.user_id, InsuranceCard.card_type == other_type
            )
        )
    ).scalar_one_or_none()
    this_mapped = map_card_result(projected)
    other_mapped = map_card_result(other.raw_ocr_json) if (other and other.raw_ocr_json) else {}
    front_mapped, back_mapped = (
        (this_mapped, other_mapped) if body.card_type == "front" else (other_mapped, this_mapped)
    )
    merged = merge_card_sides(front_mapped, back_mapped)

    info = (
        await session.execute(select(InsuranceInfo).where(InsuranceInfo.user_id == user.user_id))
    ).scalar_one_or_none()
    if info is None:
        info = InsuranceInfo(user_id=user.user_id)
        session.add(info)
    for col, value in merged.items():
        setattr(info, col, parse_iso_date(value) if col in DATE_FIELDS else value)
    info.raw_extracted = {
        body.card_type: projected,
        other_type: (other.raw_ocr_json if other else None),
    }
    info.extraction_status = "merged" if other is not None else "partial"
    info.updated_at = datetime.now(timezone.utc)

    await session.commit()

    has_front, has_back = await _sides_present(session, user.user_id)
    return CardUploadResult(
        card_type=body.card_type,
        extraction_status=extraction_status,
        insurance_info=_info_out(info, has_front, has_back),
    )


@router.get("/insurance/info", response_model=InsuranceInfoOut)
async def get_insurance_info(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> InsuranceInfoOut:
    info = (
        await session.execute(select(InsuranceInfo).where(InsuranceInfo.user_id == user.user_id))
    ).scalar_one_or_none()
    has_front, has_back = await _sides_present(session, user.user_id)
    return _info_out(info, has_front, has_back)


@router.get("/insurance/card/{card_type}/image")
async def get_card_image(
    card_type: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
):
    if card_type not in _CARD_TYPES:
        raise HTTPException(status_code=404, detail="unknown card side")
    card = (
        await session.execute(
            select(InsuranceCard).where(
                InsuranceCard.user_id == user.user_id, InsuranceCard.card_type == card_type
            )
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="no card on file")

    storage = _card_storage()
    url = storage.signed_url(card.blob_ref, minutes=15)
    if url:
        # Azure: redirect to a short-lived, PHI-free signed Blob URL.
        return RedirectResponse(url)
    # Local/CI: stream the bytes through this authed, PHI-free route.
    data = await storage.read_bytes(card.blob_ref)
    return Response(content=data, media_type=card.mime_type or "application/octet-stream")
