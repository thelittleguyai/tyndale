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
    example_scenarios: list[str] = Field(
        default_factory=list,
        description=(
            "Phase 2L — 3-5 factual, second-person past-tense scenarios of what a typical "
            "patient would have experienced for this category of service ('You'd typically "
            "have spent 1-2 hours in the ER'). Aids recall; NEVER a clinical judgment."
        ),
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


class DocumentExtraction(BaseModel):
    """Per-document extraction provenance for the encounter/admin UI — so the user can see
    which uploads were read and which failed, and never mistakes a degraded audit for a real
    one. Populated on both the success and the extraction_failed paths."""

    filename: str
    document_type: str | None = None
    extraction_status: str = Field(description="'extracted' | 'error' | 'unreadable' | ...")
    ocr_text_chars: int = Field(default=0, description="Length of the extracted OCR text")


class ExtractResult(BaseModel):
    case_file_id: str
    # 'extraction_failed' — real OCR/translate produced nothing (unreadable docs); we degrade
    # VISIBLY rather than fabricate line items. 'not_a_bill' — the doc(s) read fine but none is a
    # bill/EOB, so there's nothing to audit. Either way the UI shows an honest message + re-upload
    # CTA and never a 0-item encounter screen.
    status: Literal["encounter_verification_pending", "extraction_failed", "not_a_bill"]
    line_items: list[LineItem]
    intro_message: str = Field(
        description="The 'Tyndale double-checking on your behalf' framing for the UI header"
    )
    # Set only when status == 'extraction_failed': the honest, user-facing reason.
    extraction_message: str | None = None
    # Per-document extraction provenance (which uploads were read, which failed).
    documents: list[DocumentExtraction] = Field(default_factory=list)


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
