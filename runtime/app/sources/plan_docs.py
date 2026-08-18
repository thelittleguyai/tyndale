"""Plan-level document lookups (2026-08-19, settings item 5).

The SBC's home is the user, not the case. These helpers answer the two questions the
audit machinery asks: "does this user have a plan-level SBC on file?" (satisfies the
SBC line on every case's needs/unlock-more checklist) and "what coverage terms did it
yield?" (the rung-2 fallback when a case has no coverage of its own — the case's own
documents still WIN field-by-field, same document-evidence-wins rule as jurisdiction).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.plan_documents import PlanDocument

# The classifier types that satisfy the SBC checklist line. Cards have their own home
# (the Insurance section); an off-family upload (a bill filed here by mistake) is
# stored but never silently counted as the plan summary.
SBC_FAMILY = frozenset({"plan_summary"})


async def plan_sbc_state(
    session: AsyncSession, user_id: UUID
) -> tuple[bool, dict[str, Any] | None]:
    """(present, coverage_terms) for the user's plan-level SBC.

    ``present`` is True when ANY SBC-family plan document exists — even one whose term
    extraction read nothing (the user provided the document; asking again would be
    dishonest). ``coverage_terms`` is the newest non-empty extraction, or None.
    """
    rows = (
        (
            await session.execute(
                select(PlanDocument.document_type, PlanDocument.coverage)
                .where(PlanDocument.user_id == user_id)
                .order_by(PlanDocument.uploaded_at.desc())
            )
        )
        .all()
    )
    present = any(r.document_type in SBC_FAMILY for r in rows)
    coverage = next(
        (
            r.coverage
            for r in rows
            if r.document_type in SBC_FAMILY and isinstance(r.coverage, dict) and r.coverage
        ),
        None,
    )
    return present, coverage


def merge_case_coverage(
    case_coverage: dict[str, Any] | None, plan_coverage: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Effective coverage terms for one case: the case's own coverage wins per field;
    the plan-level SBC fills what the case doesn't state. None when neither has anything
    (rung-2 then falls back to priors exactly as before)."""
    if not plan_coverage:
        return case_coverage
    merged = dict(plan_coverage)
    for k, v in (case_coverage or {}).items():
        if v is not None:
            merged[k] = v
    return merged or None
