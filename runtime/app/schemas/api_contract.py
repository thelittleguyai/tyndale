"""Request/response models per route."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    status: str = Field(description="'ok' or 'unavailable'")
    database: str = Field(description="'ok' or 'unavailable'")


class UploadResponse(BaseModel):
    case_file_id: str
    document_id: str
    filename: str
    received_bytes: int
    note: str = "Stub — file content is not persisted in Phase 1C"


class AuditRequest(BaseModel):
    case_file_id: str


class FeedbackResponse(BaseModel):
    stored: bool
    feedback_event_id: str
    queued_for_triage: bool = False
