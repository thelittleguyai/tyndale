"""Pydantic contracts for the guided intake wizard (Phase CO-1A).

Mirrors packages/shared/src/intake.ts one-for-one (runtime is the contract owner).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# There is NO canonical step order any more (doc 40 §A4): the Intake Planner picks the next
# screen from app.intake.planner.SCREEN_REGISTRY after every capture. `current_step` on the
# wire is the planner's pick — a registry screen id, or "READY".


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


class IntakeProgress(BaseModel):
    """The segmented bar (§A8). It never regresses: `segments[].filled` includes the persisted
    high-water mark, and `note` explains a segment a reclassified document no longer backs."""

    segments: list[dict[str, Any]] = Field(default_factory=list)
    filled: int = 0
    total: int = 7
    line: str | None = None  # "1 of 7 — nice start"; never a bare "Step N of M"
    note: str | None = None
    glosses: dict[str, Any] = Field(default_factory=dict)
    high_water: list[str] = Field(default_factory=list)


class IntakeResume(BaseModel):
    """"Pick up where you left off" (§C7) — shown when the user returns to /intake with an
    unfinished guided case. `link_expiry` states the REAL magic-link lifetime."""

    case_file_id: str
    title: str | None = None
    body: str | None = None
    primary: str | None = None
    new: str | None = None
    link_expiry: str | None = None


class IntakeStateResponse(BaseModel):
    # None until the user starts (POST /intake/start): opening the landing creates nothing.
    case_file_id: str | None = None
    intake_status: str  # not_started | in_progress | complete
    intake_mode: str = "guided"
    current_step: str  # the planner's pick: a SCREEN_REGISTRY id, or "READY"
    completed_steps: list[str] = Field(default_factory=list)  # filled progress groups
    # The screen to draw: id, kind, copy (registry strings), data, example?, help?, skippable.
    screen: dict[str, Any] = Field(default_factory=dict)
    progress: IntakeProgress = Field(default_factory=IntakeProgress)
    chrome: dict[str, str] = Field(default_factory=dict)
    resume: IntakeResume | None = None
    captured_data: CapturedData
    missing_items: list[str] = Field(default_factory=list)
    # CO-12C: a pending PlanLibrary proposal (rendered by the plan_rules_confirm screen).
    plan_proposal: PlanProposal | None = None


class StepAck(IntakeStateResponse):
    """Returned by every intake write. It IS the next state — the client never decides where
    to go, it draws `screen`. `confirmations` carries low-confidence card fields (P1)."""

    confirmations: list[ConfirmationPrompt] = Field(default_factory=list)


class IntakeAnswerRequest(BaseModel):
    """One answer from one screen. `action`: continue | skip | ack | yes | no | not_sure | fix.
    `values` is screen-specific and validated by the route against that screen's fields."""

    case_file_id: str
    screen: str
    action: str = "continue"
    values: dict[str, Any] = Field(default_factory=dict)


class IntakeRunResponse(BaseModel):
    case_file_id: str
    status: str
    # Where the app goes next — the EXISTING reveal/thread; the guided route builds no results UI.
    next_route: str
    conversation_id: str | None = None


class IntakeHandoffRequest(BaseModel):
    case_file_id: str


class HelpEmailRequest(BaseModel):
    case_file_id: str | None = None
    document_type: str
    screen: str | None = None


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
