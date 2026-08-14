"""FeedbackEvent schema — matches docs/tyndale-spec/L05_feedback_consent_schema.md."""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

FeedbackType = Literal[
    "thumbs",
    "structured_correction",
    "outcome_report",
    "value_confirmation",
    "implicit_signal",
]

StructuredReason = Literal[
    "wrong_number",
    "missed_an_error",
    "false_error",
    "bad_recommendation",
    "confusing",
    "wrong_citation",
    "wrong_coverage_reading",
    "other",
]


class FeedbackOutcome(BaseModel):
    acted_on_recommendation: bool | None = None
    resolved: Literal["yes", "no", "partial", "pending", "unknown"] | None = None
    amount_saved: float | None = None
    outcome_notes: str | None = None


class ValueConfirmation(BaseModel):
    # confirmation_kind distinguishes a generic extracted-value confirmation
    # from an encounter line-item confirmation (Phase 2I / L07 step 4).
    confirmation_kind: Literal["extracted_value", "encounter_lineitem"] | None = None
    field: str | None = None
    tyndale_extracted: str | None = None
    user_corrected: str | None = None
    was_correct: bool | None = None


class FeedbackEventIn(BaseModel):
    # Required (per L05 capture_schema.json)
    event_id: str
    timestamp: datetime.datetime
    case_file_id: str
    feedback_type: FeedbackType
    # Optional
    user_id: str | None = None
    response_id: str | None = Field(default=None, description="Which Tyndale response this is about")
    thumbs: Literal["up", "down"] | None = None
    structured_reason: list[StructuredReason] | None = None
    free_text: str | None = None
    outcome: FeedbackOutcome | None = None
    # What happened on ONE call the user made, tapped in call mode (H6). Typed rather than
    # smuggled through outcome_notes so nothing has to sniff a string for meaning (DL-39), and
    # deliberately NOT an `outcome`: none of the three routes resolves a case, so this must
    # never reach the recovered tally or permanently retire the outcome follow-up.
    call_outcome: Literal["fixing_it", "pushed_back", "left_message"] | None = None
    value_confirmation: ValueConfirmation | None = None
    # improvement_consent on the request body is IGNORED by the server — the
    # POST /v1/feedback route reads the user's current consent from the users
    # table at insert time (never trust the client's claimed value).
    improvement_consent: bool = False
    promoted_to_eval: bool = False
    linked_golden_example_id: str | None = None


# --- Phase 2J response/query shapes -----------------------------------------
class FeedbackAck(BaseModel):
    event_id: str
    feedback_event_id: str
    queued_for_deid: bool


class FeedbackEventOut(BaseModel):
    """Projection of a stored feedback_event for the audit-results screen to
    restore per-target rating state across navigation."""

    feedback_event_id: str
    feedback_type: str
    response_id: str | None = None
    thumbs: Literal["up", "down"] | None = None
    structured_reason: list[str] | None = None
    created_at: str


class CaseFeedbackPayload(BaseModel):
    case_file_id: str
    events: list[FeedbackEventOut] = Field(default_factory=list)


class OutcomePrompt(BaseModel):
    case_file_id: str
    days_since_recommendation: int
    finding_summary: str = Field(description="e.g. 'Cost sharing miscalculation with UnitedHealthcare'")


class OutcomePromptsPayload(BaseModel):
    prompts: list[OutcomePrompt] = Field(default_factory=list)


class UserProfile(BaseModel):
    id: str
    first_name: str
    email: str
    user_type: Literal["user", "admin"]
    improvement_consent: bool
    created_at: str


class ConsentUpdate(BaseModel):
    improvement_consent: bool


class ConsentHistoryEntry(BaseModel):
    changed_at: str
    from_consent: bool
    to_consent: bool


class ConsentHistoryPayload(BaseModel):
    user_id: str
    history: list[ConsentHistoryEntry] = Field(default_factory=list)
