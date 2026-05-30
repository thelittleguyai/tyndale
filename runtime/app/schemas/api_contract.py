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
    """Legacy single-file response — kept for the 14-day backwards-compat window
    (the singular file=... request shape)."""

    case_file_id: str
    document_id: str
    filename: str
    received_bytes: int
    note: str = "Stub — file content is not persisted in Phase 1C"


class UploadedDoc(BaseModel):
    document_id: str
    filename: str
    document_type: str = Field(
        description="bill | eob | insurance_card | plan_summary | denial_letter | collections_notice | other"
    )
    classification_confidence: float = 0.0
    size_bytes: int


class MultiUploadResponse(BaseModel):
    """Phase 2L — multi-document upload. One entry per file, all attached to one
    case file (created, or appended to an existing case_file_id)."""

    case_file_id: str
    uploads: list[UploadedDoc]


class AuditRequest(BaseModel):
    case_file_id: str


class FeedbackResponse(BaseModel):
    stored: bool
    feedback_event_id: str
    queued_for_triage: bool = False
