"""Pydantic schemas for the chat surface (Phase CO-10).

Covers conversation CRUD shapes, the message shape, and the structured chat
sub-objects (tiered content chunks, citations, tool calls) that persist in the
``messages`` JSONB columns and are echoed over the SSE stream.

The SSE wire events themselves are documented in ``docs/chat.md`` and built as
plain dicts in ``app/agents/chat.py`` / ``app/routes/messages.py``; the
``ChatStreamEvent`` mirror here exists for the shared TS contract.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

ChatMode = Literal["per_case", "freeform"]
VoiceTier = Literal["A", "B", "C"]
MessageRole = Literal["user", "assistant", "system"]
MessageStatus = Literal["streaming", "complete", "stopped", "failed"]


# --- structured chat sub-objects -------------------------------------------


class Citation(BaseModel):
    """A grounded source reference. ``action_type`` carries the freeform-mode
    ``create_case_cta`` so the UI can render a button (it rides the citations
    array per the CO-10 spec)."""

    source_id: str | None = None
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    effective_date: str | None = None
    payer: str | None = None
    # CPT code surfaced WITHOUT the AMA-copyrighted descriptor (DL-54).
    cpt_code: str | None = None
    action_type: Literal["create_case_cta"] | None = None
    # laws_regulations X6 fields (DL-84): surfaced so the UI/model can voice a legal
    # claim as CATEGORICAL (flat rule) vs CONDITIONAL (fact-dependent), and show how
    # current the classification is. Null for non-law citations (codes, payer policy).
    as_of: str | None = None
    x6_classification: Literal["CATEGORICAL", "CONDITIONAL"] | None = None


class ContentChunk(BaseModel):
    """One tiered section of an assistant message (A facts / B legal+cite / C
    strategic)."""

    tier: VoiceTier
    text: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float | None = None


class ToolCall(BaseModel):
    tool_name: str
    subagent: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    timestamp: str | None = None
    duration_ms: int | None = None


# --- conversation CRUD ------------------------------------------------------


class ConversationCreate(BaseModel):
    case_id: uuid.UUID | None = None


class ConversationPatch(BaseModel):
    title: str | None = None
    is_archived: bool | None = None


class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    case_id: uuid.UUID | None
    mode: ChatMode
    title: str | None
    is_archived: bool
    message_count: int
    last_message_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# Chat-first typed thread entries (DL-91). 'message' = the classic text/chunks turn; the rest are
# bridge-authored (role='system') cards whose structured data rides in `payload`.
MessageKind = Literal[
    "message", "status_card_update", "system_message", "moment_card", "verification_request",
    "verification_suggestion",
    # CS1's attest-and-proceed ask. The bridge has written this kind since 2026-08-11, but no
    # thread CONTAINED one until the e2e identity fix made the gate fire (2026-08-18) — at
    # which point GET /v1/conversations/{id} 500'd on every attest-gated thread because this
    # Literal didn't know the kind. test_thread_kinds pins bridge-written ⊆ MessageKind.
    "attest_request",
]


class MessageOut(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sequence_number: int
    role: MessageRole
    kind: MessageKind = "message"
    payload: dict | None = None
    content: str | None
    content_chunks: list[ContentChunk] | None = None
    tool_calls: list[ToolCall] | None = None
    citations: list[Citation] | None = None
    confidence_overall: float | None = None
    # Tap-to-reply chips (item 3, 2026-08-22) — present on freeform assistant turns.
    suggested_replies: list[str] | None = None
    status: MessageStatus
    error_message: str | None = None
    token_usage_input: int | None = None
    token_usage_output: int | None = None
    estimated_cost_usd: float | None = None
    created_at: datetime.datetime
    completed_at: datetime.datetime | None = None


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class ConversationList(BaseModel):
    conversations: list[ConversationOut]
    total: int
    limit: int
    offset: int


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


# --- SSE stream event mirror (shared TS contract) ---------------------------

ChatStreamEventType = Literal[
    "user_message_persisted",
    "assistant_message_started",
    "tool_call_started",
    "tool_call_completed",
    "token",
    "citation_added",
    "assistant_message_completed",
    "error",
    "done",
]


class ChatStreamEvent(BaseModel):
    event: ChatStreamEventType
    data: dict[str, Any] = Field(default_factory=dict)
