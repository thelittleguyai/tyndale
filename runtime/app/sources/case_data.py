"""Shared case-data access + value parsing for the accumulator adapters (CO-12B).

The AccumulatorSource adapters read CaseFile.eobs / CaseFile.coverage. This loader
opens its own async session (mirroring app.agents.orchestrator) and degrades
gracefully: an invalid or unknown case_file_id yields empty data rather than
raising, so the engine still returns a valid (empty, low-confidence) result.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile


async def load_case_eobs_coverage(case_file_id: str) -> tuple[list[dict], dict | None]:
    """Return (eobs, coverage) for a case, or ([], None) if the id is invalid or the
    case doesn't exist. Never raises on a bad id (graceful degradation)."""
    try:
        cf_uuid = UUID(str(case_file_id))
    except (ValueError, AttributeError, TypeError):
        return [], None
    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == cf_uuid))
        ).scalar_one_or_none()
    if case is None:
        return [], None
    return list(case.eobs or []), case.coverage


async def load_case_coverage_and_plan(case_file_id: str) -> tuple[dict | None, dict | None]:
    """Return (coverage, plan_current) for a case, or (None, None) if the id is
    invalid or the case doesn't exist. Used by the PlanLibrary CoverageSource."""
    try:
        cf_uuid = UUID(str(case_file_id))
    except (ValueError, AttributeError, TypeError):
        return None, None
    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == cf_uuid))
        ).scalar_one_or_none()
    if case is None:
        return None, None
    return case.coverage, case.plan_current


async def load_case_encounter(
    case_file_id: str,
) -> tuple[list[dict], list[dict], str | None]:
    """Return (line_items, encounter_confirmations, visit_context) for a case, or
    ([], [], None) if the id is invalid or the case doesn't exist. Never raises on a
    bad id (graceful degradation). Reads the Phase-2I encounter data on CaseFile —
    the source for the ClinicalEncounterSource shim (CO-12D)."""
    try:
        cf_uuid = UUID(str(case_file_id))
    except (ValueError, AttributeError, TypeError):
        return [], [], None
    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == cf_uuid))
        ).scalar_one_or_none()
    if case is None:
        return [], [], None
    return list(case.line_items or []), list(case.encounter_confirmations or []), case.visit_context


def parse_iso_date(value: Any) -> date | None:
    """Parse an ISO-ish date string to a date, or None. Tolerant of trailing time."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def as_float(value: Any) -> float | None:
    """Coerce a numeric value to float, or None (bools are not numbers here)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
