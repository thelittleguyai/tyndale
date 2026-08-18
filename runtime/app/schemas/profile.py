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


class ProfilePatch(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    accept_terms: bool | None = None
    email_notifications_enabled: bool | None = None


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
