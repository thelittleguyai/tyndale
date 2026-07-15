"""POST /v1/events request/response shapes (Internal Analytics P0).

Client-side events for the few facts NOT server-known (e.g. call-mode step views). Server-known
funnel events are emitted server-side and are rejected here (the client is never trusted for
funnel truth). Unknown / server-only / not-yet-live names are silently dropped with a counter —
a bad client can never 4xx-storm the batch endpoint."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    name: str
    # enums/numbers/booleans only — validated against the registry server-side (free text is
    # structurally impossible to store, so anything non-conforming is dropped).
    properties: dict = Field(default_factory=dict)
    case_file_id: uuid.UUID | None = None


class EventBatch(BaseModel):
    events: list[EventIn] = Field(default_factory=list, max_length=50)


class EventBatchResult(BaseModel):
    accepted: int
    dropped: int
