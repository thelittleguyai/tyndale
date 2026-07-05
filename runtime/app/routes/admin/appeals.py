"""Admin read-only view of appeal tracks (Sprint G, shadow-mode DL-55/56).

Appeals case management stays dark for users (ENABLE_APPEALS_CASEMGMT=false); this admin-only
endpoint lets the team watch the escalation-ladder state accumulate. Read-only — no
transitions are exposed here. DL-60: non-admin → 404.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appeals.tracks import next_states
from app.auth import CurrentUser
from app.db.models.appeal_tracks import AppealTrack
from app.db.session import get_session
from app.routes.admin._deps import admin_user, iso

router = APIRouter()


class AppealTrackOut(BaseModel):
    appeal_track_id: str
    case_file_id: str
    current_state: str
    allowed_next: list[str]
    history: list
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/admin/appeal-tracks", response_model=list[AppealTrackOut])
async def list_appeal_tracks(
    _admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> list[AppealTrackOut]:
    rows = (
        await session.execute(select(AppealTrack).order_by(AppealTrack.created_at.desc()))
    ).scalars().all()
    return [
        AppealTrackOut(
            appeal_track_id=str(t.appeal_track_id),
            case_file_id=str(t.case_file_id),
            current_state=t.current_state,
            allowed_next=list(next_states(t.current_state)),
            history=t.history or [],
            created_at=iso(t.created_at),
            updated_at=iso(t.updated_at),
        )
        for t in rows
    ]
