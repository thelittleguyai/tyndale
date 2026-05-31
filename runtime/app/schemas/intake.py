"""Pydantic contracts for the guided intake wizard (Phase CO-1A).

Mirrors packages/shared/src/intake.ts one-for-one (runtime is the contract owner).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Canonical 10-step order. The frontend route names match these exactly.
INTAKE_STEPS: list[str] = [
    "welcome",
    "insurance-card",
    "coverage-details",
    "benefits",
    "deductible",
    "oop-max",
    "bills",
    "eobs",
    "visit-context",
    "complete",
]

# Steps the user may skip (graceful degradation — equal-weight in the UI).
SKIPPABLE_STEPS: set[str] = {
    "insurance-card",
    "coverage-details",
    "benefits",
    "deductible",
    "oop-max",
    "eobs",
    "visit-context",
}


class ConfirmationPrompt(BaseModel):
    """A low-confidence extracted field for a trivial yes/no confirmation (P1)."""

    field: str
    read_value: str
    prompt: str
    confidence: float


class CapturedData(BaseModel):
    coverage: dict[str, Any] = Field(default_factory=dict)
    bills_count: int = 0
    eobs_count: int = 0
    visit_context: str | None = None


class IntakeStateResponse(BaseModel):
    case_file_id: str
    intake_status: str  # not_started | in_progress | complete
    current_step: str
    completed_steps: list[str] = Field(default_factory=list)
    captured_data: CapturedData
    missing_items: list[str] = Field(default_factory=list)


class StepAck(BaseModel):
    """Returned by step manual-entry / skip / visit-context / extract."""

    case_file_id: str
    intake_status: str
    current_step: str
    completed_steps: list[str] = Field(default_factory=list)
    confirmations: list[ConfirmationPrompt] = Field(default_factory=list)


class VisitContextRequest(BaseModel):
    case_file_id: str | None = None
    visit_context: str = Field(max_length=500)


class ExtractRequest(BaseModel):
    case_file_id: str | None = None
    document_id: str


class CompletionSummary(BaseModel):
    case_file_id: str
    intake_status: str
    captured: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    summary: str
