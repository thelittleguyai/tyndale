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
from app.schemas.profile import (
    CardUploadRequest,
    CardUploadResult,
    InsuranceInfoOut,
    SecondaryInsuranceOut,
    SecondaryInsurancePatch,
)
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
# secondary_front/back (2026-08-19, item 4): the same upload/extract/serve path stores
# the SECONDARY plan's card, keyed by type. Extraction merge stays primary-only — the
# secondary row is user-entered (B6 groundwork; COB logic is Brock's pending content).
_CARD_TYPES = ("front", "back", "secondary_front", "secondary_back")


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
        raise HTTPException(status_code=422, detail="unknown card_type")
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

    # Secondary-card sides (2026-08-19, item 4): store + OCR-project only — NEVER merge
    # into the primary insurance_info (the "other side" arithmetic below is primary-pair
    # logic, and the secondary row is user-entered; B6 groundwork).
    if body.card_type not in ("front", "back"):
        await session.commit()
        info = (
            await session.execute(select(InsuranceInfo).where(
                InsuranceInfo.user_id == user.user_id, InsuranceInfo.role == "primary"
            ))
        ).scalar_one_or_none()
        has_front, has_back = await _sides_present(session, user.user_id)
        return CardUploadResult(
            card_type=body.card_type,
            extraction_status=extraction_status,
            insurance_info=_info_out(info, has_front, has_back),
        )

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
        await session.execute(select(InsuranceInfo).where(
            InsuranceInfo.user_id == user.user_id, InsuranceInfo.role == "primary"
        ))
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
        await session.execute(select(InsuranceInfo).where(
            InsuranceInfo.user_id == user.user_id, InsuranceInfo.role == "primary"
        ))
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


# --------------------------------------------------------------------------- #
# Secondary insurance (2026-08-19, item 4) — capture-and-display only (B6
# groundwork). Intake noted has_secondary_coverage inside the case coverage
# blob; this promotes it to a real, editable role='secondary' row. NO COB
# ordering or dollar logic — that is Brock's pending content.
# --------------------------------------------------------------------------- #


async def _secondary_row(session: AsyncSession, user_id) -> InsuranceInfo | None:
    return (
        await session.execute(
            select(InsuranceInfo).where(
                InsuranceInfo.user_id == user_id, InsuranceInfo.role == "secondary"
            )
        )
    ).scalar_one_or_none()


async def _secondary_captured_hint(session: AsyncSession, user_id) -> str | None:
    """What intake's guided flow noted, surfaced while no secondary row exists yet."""
    from app.db.models.case_files import CaseFile

    rows = (
        await session.execute(
            select(CaseFile.coverage)
            .where(CaseFile.user_id == user_id)
            .order_by(CaseFile.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    for cov in rows:
        if isinstance(cov, dict) and cov.get("has_secondary_coverage"):
            return str(cov.get("secondary_coverage_detail") or "You mentioned a second plan during intake.")
    return None


def _secondary_out(
    info: InsuranceInfo | None, has_front: bool, has_back: bool, hint: str | None
) -> SecondaryInsuranceOut:
    if info is None:
        return SecondaryInsuranceOut(
            exists=False, has_front=has_front, has_back=has_back, captured_hint=hint
        )
    return SecondaryInsuranceOut(
        exists=True,
        insurer=info.insurer,
        member_id=info.member_id,
        plan_type=info.plan_type,
        has_front=has_front,
        has_back=has_back,
        captured_hint=None,
    )


async def _secondary_sides(session: AsyncSession, user_id) -> tuple[bool, bool]:
    rows = (
        (
            await session.execute(
                select(InsuranceCard.card_type).where(InsuranceCard.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    return "secondary_front" in rows, "secondary_back" in rows


@router.get("/insurance/secondary", response_model=SecondaryInsuranceOut)
async def get_secondary_insurance(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> SecondaryInsuranceOut:
    info = await _secondary_row(session, user.user_id)
    hint = None if info else await _secondary_captured_hint(session, user.user_id)
    front, back = await _secondary_sides(session, user.user_id)
    return _secondary_out(info, front, back, hint)


@router.put("/insurance/secondary", response_model=SecondaryInsuranceOut)
async def put_secondary_insurance(
    body: SecondaryInsurancePatch,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> SecondaryInsuranceOut:
    from app.plan_types import PLAN_TYPES

    if body.plan_type is not None and body.plan_type != "" and body.plan_type not in PLAN_TYPES:
        raise HTTPException(status_code=422, detail="invalid plan_type")
    info = await _secondary_row(session, user.user_id)
    if info is None:
        info = InsuranceInfo(user_id=user.user_id, role="secondary")
        session.add(info)
    if body.insurer is not None:
        info.insurer = body.insurer.strip() or None
    if body.member_id is not None:
        info.member_id = body.member_id.strip() or None
    if body.plan_type is not None:
        info.plan_type = body.plan_type or None
    info.updated_at = datetime.now(timezone.utc)
    await session.commit()
    front, back = await _secondary_sides(session, user.user_id)
    return _secondary_out(info, front, back, None)


@router.delete("/insurance/secondary", status_code=204)
async def delete_secondary_insurance(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    info = await _secondary_row(session, user.user_id)
    if info is not None:
        await session.delete(info)
    for ct in ("secondary_front", "secondary_back"):
        card = (
            await session.execute(
                select(InsuranceCard).where(
                    InsuranceCard.user_id == user.user_id, InsuranceCard.card_type == ct
                )
            )
        ).scalar_one_or_none()
        if card is not None:
            await session.delete(card)
    await session.commit()
    return Response(status_code=204)
