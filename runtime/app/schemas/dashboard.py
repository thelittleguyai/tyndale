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


class ActiveCase(BaseModel):
    """A resumable case for the dashboard's status-aware Open Cases card. Covers the FULL
    lifecycle (not just pre-audit), so a user mid-audit or with results ready always has a way
    back in — the gap the intake-only resume card left."""

    case_file_id: str
    status: str = Field(description="raw case status")
    label: str = Field(description="user-facing status, e.g. 'Verify your visit', 'Results ready'")
    # Which screen resumes this case: the encounter-verification screen (pre-audit) or the audit
    # results/progress screen. The audit results screen would spin forever on a pre-encounter
    # case, so this must be status-driven, not a single hard-coded route.
    resume: Literal["encounter", "results"]
    days_open: int = 0
    next_deadline_date: date | None = None
    next_deadline_label: str | None = None


class HomeBanner(BaseModel):
    """Welcome banner (Brock mockups, honest subset): registry-authored copy whose subline
    is derived ONLY from real computed case state — never an unbuilt-feature claim (B8)."""

    title: str
    subline: str


# --- Top-level payloads ------------------------------------------------------
class DashboardPayload(BaseModel):
    user: UserBrief
    banner: HomeBanner | None = None
    coverage: CoverageSummary
    amount_saved_ytd: float
    # Brock mockups item 3 — the two honest stat cards. recovered_to_date sums CONFIRMED
    # recovered amounts from outcome reports (never the payer-gap proxy above); the client
    # renders a neutral empty state when it is 0 — never "$0.00" as a sad zero.
    recovered_to_date: float = 0.0
    open_count: int = 0
    needs_you_count: int = 0
    # Phase CO-1A — drives the intake gate. 'complete' users see the dashboard;
    # others are routed into the wizard (resuming at intake_current_step).
    intake_status: str = "complete"
    intake_current_step: str | None = None
    # Whether the user has ANY case file. The gate uses this so the wizard is mandatory only
    # for brand-new users — anyone with case history is never hard-redirected (2026-07-06 fix).
    has_cases: bool = False
    open_cases: list[OpenCase] = Field(default_factory=list)
    # Status-aware, full-lifecycle resumable cases for the Open Cases card (2026-07-06). Distinct
    # from open_cases (which stays pre-audit-only and feeds the status-forward greeting).
    active_cases: list[ActiveCase] = Field(default_factory=list)
    # Phase 2J — cases eligible for an outcome follow-up prompt (scripted
    # recommendation given > N days ago, no outcome reported yet). Each item is
    # an app.schemas.feedback.OutcomePrompt dict; inlined as dict to avoid a
    # cross-schema import cycle.
    outcome_prompts: list[dict] = Field(default_factory=list)
    status_forward_greeting: str | None = None
    # DL-91 D5: when true, the client shows the Tyndale Record (sub-case rows) in place of the
    # ad-hoc Open Cases list. Reflects the server's enable_record_view flag.
    record_enabled: bool = False


class CasesListPayload(BaseModel):
    cases: list[CaseSummary] = Field(default_factory=list)


class CoverageDetailPayload(BaseModel):
    coverage: CoverageSummary
    source_document_ids: list[str] = Field(default_factory=list)
    confidence: dict = Field(default_factory=dict)
