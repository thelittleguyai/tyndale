"""Profile + insurance API shapes (CO-17).

These responses surface a SUBSET of insurance_info — never the raw extracted JSON,
and the route layer keeps member_id / DOB / names out of logs + URLs.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel


class ProfileState(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    email: str
    profile_completed: bool
    has_insurance_card: bool
    # Reminders preference (2026-08-19): gates nudge chases + check-ins ONLY — transactional
    # mail (audit-ready, recovery, magic links) is service mail and never consults it.
    email_notifications_enabled: bool = True
    # State of residence + optional mailing address (2026-08-19, settings item 2). State is
    # the load-bearing jurisdiction field; suggested_state is a document-derived PREFILL the
    # user confirms (populate-don't-ask) — present only while state is unset.
    state: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    zip_code: str | None = None
    suggested_state: str | None = None


class ProfilePatch(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    accept_terms: bool | None = None
    email_notifications_enabled: bool | None = None
    state: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    zip_code: str | None = None


class SecondaryInsuranceOut(BaseModel):
    """The secondary plan (2026-08-19, item 4) — display + edit surface only; COB math is
    Brock's pending content (B6). captured_hint carries what intake's guided flow noted
    (has_secondary_coverage + detail from the case coverage blob) while no row exists."""

    exists: bool = False
    insurer: str | None = None
    member_id: str | None = None
    plan_type: str | None = None
    has_front: bool = False
    has_back: bool = False
    captured_hint: str | None = None


class SecondaryInsurancePatch(BaseModel):
    insurer: str | None = None
    member_id: str | None = None
    plan_type: str | None = None


class InsuranceInfoOut(BaseModel):
    insurer: str | None = None
    plan_name: str | None = None
    plan_type: str | None = None
    member_id: str | None = None
    group_number: str | None = None
    member_name: str | None = None
    effective_date: date | None = None
    rx_bin: str | None = None
    rx_pcn: str | None = None
    copays: Any | None = None
    extraction_status: str | None = None
    has_front: bool = False
    has_back: bool = False


class CardUploadRequest(BaseModel):
    card_type: str  # 'front' | 'back'
    image_base64: str
    mime_type: str
    file_size: int | None = None


class CardUploadResult(BaseModel):
    card_type: str
    extraction_status: str
    insurance_info: InsuranceInfoOut
