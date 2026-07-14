"""Tyndale Record API shapes (D5, Phase C)."""

from __future__ import annotations

from pydantic import BaseModel


class DeadlineInfo(BaseModel):
    label: str
    due_date: str | None = None
    source: str  # provenance (appeals rule source, or the deadline_type)


class ThreeNumberBrief(BaseModel):
    provider_billed: float
    eob_member_responsibility: float
    tyndale_computed: float


class SubCaseRow(BaseModel):
    case_file_id: str
    service_date: str | None = None  # best-effort; null until a structured visit date is extracted
    provider: str | None = None
    status: str
    label: str
    resume: str  # 'summary' (results-bearing) | 'thread' (in-flight)
    three_number: ThreeNumberBrief | None = None  # null → the row shows needs-documents, not {0,0,0}
    open_item_count: int = 0
    next_deadline: DeadlineInfo | None = None
    recovered_so_far: float = 0.0  # CONFIRMED only


class RecordAggregates(BaseModel):
    total_billed_reviewed: float
    total_recovered: float  # CONFIRMED outcomes only, shown "so far"
    total_identified: float  # audit ESTIMATE (finding gap) — labeled separately, never recovered
    open_items: int
    next_check_in_date: str | None = None


class RecordPayload(BaseModel):
    window_months: int
    sub_cases: list[SubCaseRow]
    aggregates: RecordAggregates
    has_older: bool = False  # older-than-window cases exist → "full history"
