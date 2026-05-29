"""Pydantic models for the dashboard / cases / coverage routes.

Shapes mirror packages/shared/src/dashboard.ts one-for-one.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


# --- User --------------------------------------------------------------------
class UserBrief(BaseModel):
    id: str
    first_name: str


# --- Coverage components -----------------------------------------------------
class CoverageMeter(BaseModel):
    total: float
    met: float
    remaining: float


class CopayAmount(BaseModel):
    amount: float


class CoverageCopays(BaseModel):
    pcp_visit: CopayAmount
    er_visit: CopayAmount
    specialist: CopayAmount


CoverageExtractionStatus = Literal["extracted", "pending", "missing"]


class CoverageSummary(BaseModel):
    deductible: CoverageMeter | None = None
    oop_max: CoverageMeter | None = None
    copays: CoverageCopays | None = None
    extraction_status: CoverageExtractionStatus = "missing"


# --- Cases -------------------------------------------------------------------
class OpenCase(BaseModel):
    case_file_id: str
    headline: str
    days_open: int
    next_deadline_date: date | None = None
    next_deadline_label: str | None = None


class CaseSummary(BaseModel):
    case_file_id: str
    headline: str
    status: str
    last_updated: str = Field(description="ISO-8601 timestamp")


# --- Top-level payloads ------------------------------------------------------
class DashboardPayload(BaseModel):
    user: UserBrief
    coverage: CoverageSummary
    amount_saved_ytd: float
    open_cases: list[OpenCase] = Field(default_factory=list)
    # Phase 2J — cases eligible for an outcome follow-up prompt (scripted
    # recommendation given > N days ago, no outcome reported yet). Each item is
    # an app.schemas.feedback.OutcomePrompt dict; inlined as dict to avoid a
    # cross-schema import cycle.
    outcome_prompts: list[dict] = Field(default_factory=list)
    status_forward_greeting: str | None = None


class CasesListPayload(BaseModel):
    cases: list[CaseSummary] = Field(default_factory=list)


class CoverageDetailPayload(BaseModel):
    coverage: CoverageSummary
    source_document_ids: list[str] = Field(default_factory=list)
    confidence: dict = Field(default_factory=dict)
