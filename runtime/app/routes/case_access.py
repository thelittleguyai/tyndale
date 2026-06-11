"""Shared case-file ownership check for the audit/encounter route family.

Security fix: these routes previously took any case_file_id with no auth,
allowing IDOR access to other users' cases (PHI). Every route that operates on
a case must resolve the current user and verify ownership.

404 (not 403) covers both not-found and not-owned — anti-enumeration, matching
the pattern in upload.py.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.case_files import CaseFile


def validate_case_uuid(case_file_id: str) -> UUID:
    try:
        return UUID(case_file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="case_file_id must be a UUID") from None


async def require_case_owner(
    case_file_id: str,
    user: CurrentUser,
    session: AsyncSession,
) -> CaseFile:
    """Load the case file and 404 unless it exists and belongs to ``user``."""
    cf_uuid = validate_case_uuid(case_file_id)
    case = (
        await session.execute(select(CaseFile).where(CaseFile.case_file_id == cf_uuid))
    ).scalar_one_or_none()
    if case is None or case.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="case_file not found")
    return case
