"""Account-deletion PHI scrub (Phase 2.4), shared by the admin soft-delete route and the
member-facing self-service delete.

Nulls/anonymizes identity, deletes the identified insurance rows AND their card-image blobs,
and bumps jwt_version to invalidate outstanding sessions. The user_id, case files, and audit
trail are PRESERVED (HIPAA retention + anti-enumeration — a re-signup can't confirm the prior
account). The caller sets soft_deleted_by, writes the audit row, and commits.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import structlog
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.insurance_info import InsuranceInfo
from app.db.models.users import User
from app.ingestion.blob_storage import BlobStorage

log = structlog.get_logger(__name__)


async def scrub_user_account(user: User, session: AsyncSession) -> dict:
    """Scrub identity + delete insurance PHI (rows + card blobs) + invalidate sessions.

    Sets soft_deleted_at + jwt_version on ``user`` and deletes its insurance rows/blobs. Does
    NOT set soft_deleted_by, write an audit row, or commit — the caller owns those (admin vs
    self differ). Call only when user.soft_deleted_at is None (caller checks). Blob deletion is
    best-effort: a storage error is logged, never fails the DB scrub, so the account still goes.
    """
    digest = hashlib.sha256((user.email or "").encode("utf-8")).hexdigest()[:8]
    user.email = f"deleted-{digest}@deleted.tyndaleapp.net"
    user.phone = None
    user.first_name = None
    user.last_name = None
    user.date_of_birth = None
    user.soft_deleted_at = datetime.now(timezone.utc)
    user.jwt_version = (user.jwt_version or 1) + 1  # invalidates all outstanding tokens

    # Delete the insurance-card IMAGE blobs (uploads container) before dropping the rows.
    cards = (
        (await session.execute(select(InsuranceCard).where(InsuranceCard.user_id == user.user_id)))
        .scalars()
        .all()
    )
    storage = BlobStorage(container=get_settings().azure_storage_uploads_container)
    blobs_deleted = 0
    for card in cards:
        if not card.blob_ref:
            continue
        try:
            if await storage.delete(card.blob_ref):
                blobs_deleted += 1
        except Exception as exc:  # noqa: BLE001 — a storage error must not block the DB scrub
            log.error(
                "account_scrub.blob_delete_failed",
                user_id=str(user.user_id),
                blob_ref=card.blob_ref,
                error_class=type(exc).__name__,
            )

    # Delete the identified insurance rows (member ids/names/DOBs — pure PHI, no retention basis).
    cards_deleted = (
        await session.execute(sa_delete(InsuranceCard).where(InsuranceCard.user_id == user.user_id))
    ).rowcount or 0
    info_deleted = (
        await session.execute(sa_delete(InsuranceInfo).where(InsuranceInfo.user_id == user.user_id))
    ).rowcount or 0

    return {
        "identity_fields_nulled": ["first_name", "last_name", "date_of_birth", "phone"],
        "email_anonymized": True,
        "insurance_info_rows_deleted": int(info_deleted),
        "insurance_card_rows_deleted": int(cards_deleted),
        "insurance_card_blobs_deleted": int(blobs_deleted),
    }
