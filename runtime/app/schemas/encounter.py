"""Encounter-verification API shapes (Phase 2I).

Mirrors packages/shared/src/encounter.ts one-for-one.

The flow: extract (Bill Detective translates each line item to plain language)
-> the user confirms each via the encounter UI -> finalize (Bill Detective
re-diagnoses with confirmations as ground truth, Math Person runs the audit).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LineItemResponse = Literal["yes", "no", "not_sure"]


class LineItem(BaseModel):
    """One charged line item, translated to plain language for the user.

    Per L07 + refusals.md: the translation + context describe WHAT HAPPENED
    (a fact the user can confirm against their lived experience), NEVER a
    clinical judgment about whether the service should have happened.
    """

    line_item_id: str
    code: str
    code_system: str = Field(description="CPT | HCPCS | ICD-10")
    raw_description: str = Field(description="What the bill literally says")
    plain_language_translation: str = Field(description="Bill Detective's plain English")
    plain_language_context: str = Field(
        default="",
        description="Informational, non-leading context, e.g. 'Appendectomies are usually under two hours'",
    )
    high_risk: bool = Field(
        default=False,
        description="E/M levels, time-based codes, etc. — where upcoding/phantom risk concentrates",
    )
    billed_amount: float | None = None
    units: int | None = None


class LineItemConfirmation(BaseModel):
    line_item_id: str
    response: LineItemResponse
    user_note: str | None = None


class ExtractResult(BaseModel):
    case_file_id: str
    status: Literal["encounter_verification_pending"]
    line_items: list[LineItem]
    intro_message: str = Field(
        description="The 'Tyndale double-checking on your behalf' framing for the UI header"
    )


class ConfirmationsRequest(BaseModel):
    confirmations: list[LineItemConfirmation]


class ConfirmationsAccepted(BaseModel):
    case_file_id: str
    status: str = "audit_running"
    confirmations_recorded: int
    mismatches: int = Field(description="how many became encounter_mismatch candidate findings")


class AuditStatusResponse(BaseModel):
    case_file_id: str
    status: str = Field(
        description="open | encounter_verification_pending | encounter_verified | "
        "audit_running | audit_complete | ..."
    )


# Default intro copy (used when the agent doesn't supply one). Tone per L07:
# Tyndale double-checking on the user's behalf — not an interrogation.
DEFAULT_INTRO_MESSAGE = (
    "Insurers and billing systems make mistakes, so I want to make sure you were "
    "actually billed for what you got. Here's what you were billed for, in plain "
    "terms — does each of these match what actually happened? Not sure? That's a "
    "real option — never force a confirmation when you're unsure."
)
