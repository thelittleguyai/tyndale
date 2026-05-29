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
    value_confirmation: ValueConfirmation | None = None
    improvement_consent: bool = False
    promoted_to_eval: bool = False
    linked_golden_example_id: str | None = None
