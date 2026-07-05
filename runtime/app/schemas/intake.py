"""Pydantic contracts for the guided intake wizard (Phase CO-1A).

Mirrors packages/shared/src/intake.ts one-for-one (runtime is the contract owner).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Canonical step order. The frontend route names match these exactly. The
# coverage-regime-confirm step (Sprint B, DL-82) sits right after the card so the
# regime is settled before benefits are captured under the wrong population's rules.
INTAKE_STEPS: list[str] = [
    "welcome",
    "insurance-card",
    "coverage-regime-confirm",
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
    "coverage-regime-confirm",
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
    # Sprint B (DL-82): the case's detected/confirmed coverage regime + the detection
    # metadata (candidate/confidence/evidence/verified) the confirm screen preselects
    # from. coverage_regime is null until high-confidence detection or a user confirm.
    coverage_regime: str | None = None
    regime_detection: dict[str, Any] | None = None


class PlanProposal(BaseModel):
    """A stored plan-level benefit design proposed for one-tap confirmation (CO-12C).
    Plan-level only — no PHI. The user confirms (writes through to coverage) or
    rejects (forks a corrected design)."""

    plan_library_id: str
    payer: str
    plan_name: str | None = None
    plan_year: int
    benefit_design: dict[str, Any] = Field(default_factory=dict)
    confidence: int = 1
    summary: str


class IntakeStateResponse(BaseModel):
    case_file_id: str
    intake_status: str  # not_started | in_progress | complete
    current_step: str
    completed_steps: list[str] = Field(default_factory=list)
    captured_data: CapturedData
    missing_items: list[str] = Field(default_factory=list)
    # CO-12C: a pending PlanLibrary proposal to confirm before prompting for an SBC.
    plan_proposal: PlanProposal | None = None


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


class RegimeConfirmRequest(BaseModel):
    """The user's explicit answer to 'How are you covered?' (Sprint B ladder). The
    route validates coverage_regime against the seven regimes and marks the detection
    verified=true (user_declared)."""

    case_file_id: str | None = None
    coverage_regime: str


class CompletionSummary(BaseModel):
    case_file_id: str
    intake_status: str
    captured: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    summary: str
