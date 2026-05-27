"""Pydantic models for the four Claude Agent SDK hook surfaces + the crisis
classifier, matching docs/integration-contracts.md Section 2.1.

These types are the boundary the security/HIPAA contact implements against. The
stub implementations in this package return safe defaults; Phase 4 replaces them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Outcome = Literal["success", "error", "timeout", "blocked"]
StopAction = Literal["ship", "regenerate", "human_review"]


# --- UserPromptSubmit -------------------------------------------------------
class UserPromptSubmitInput(BaseModel):
    user_id: str = Field(description="Authenticated user id")
    case_file_id: str | None = Field(default=None, description="Active case file, if any")
    raw_message: str = Field(description="The user's raw message text")
    attached_documents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Each: {document_id, mime_type, ocr_text | None}",
    )


class UserPromptSubmitResult(BaseModel):
    scrubbed_message: str = Field(description="User message with prompt-injection patterns flagged")
    wrapped_documents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="OCR'd content wrapped in 'DATA, NOT INSTRUCTIONS' framing",
    )
    injection_signals: list[str] = Field(
        default_factory=list, description="Detected injection patterns (logged to audit)"
    )
    block: bool = Field(
        default=False,
        description="If true, the message never reaches the Lead Planner; user sees a polite notice",
    )


# --- PreToolUse -------------------------------------------------------------
class PreToolUseInput(BaseModel):
    case_file_id: str
    actor: str = Field(description="subagent name or 'lead_planner'")
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)


class PreToolUseResult(BaseModel):
    sanitized_args: dict[str, Any] = Field(
        description="Tool args with PHI scrubbed where required by destination's BAA status"
    )
    approved: bool = Field(description="If false, the tool invocation is blocked")
    block_reason: str | None = Field(default=None)


# --- PostToolUse (returns None semantically; void via raise-on-error) --------
class PostToolUseInput(BaseModel):
    case_file_id: str
    actor: str
    tool_name: str
    tool_args_scrubbed: dict[str, Any] = Field(default_factory=dict)
    tool_result: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int
    outcome: Outcome
    error_details: str | None = Field(default=None)


class PostToolUseResult(BaseModel):
    """Documentation of what the hook writes. The hook itself returns None
    (void) per the contract and raises on a write failure."""

    audit_event_id: str | None = None
    written: bool = False


# --- Stop -------------------------------------------------------------------
class StopInput(BaseModel):
    case_file_id: str
    actor: str
    generated_output: str
    retrieved_chunks: list[dict[str, Any]] = Field(
        default_factory=list, description="Chunks retrieved this session, each with a source id"
    )
    attempt: int = Field(description="Which generation attempt (1, 2, 3)")


class StopResult(BaseModel):
    resolved: bool = Field(description="True iff every citation resolves")
    unresolved_citations: list[str] = Field(default_factory=list)
    action: StopAction


# --- Crisis classifier ------------------------------------------------------
class CrisisClassifierInput(BaseModel):
    raw_message: str


class CrisisClassifierResult(BaseModel):
    crisis_detected: bool
