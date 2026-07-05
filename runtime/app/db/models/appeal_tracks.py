"""AppealTrack — the escalation-ladder state persisted per case (Sprint G, DL-55/56).

One row per case that has entered the appeal ladder. Shadow-mode: written/read only when
ENABLE_APPEALS_CASEMGMT is on (admin read-only for now); no user-facing surfaces.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppealTrack(Base):
    __tablename__ = "appeal_tracks"
    __table_args__ = (
        CheckConstraint(
            "current_state IN ('call', 'supervisor', 'internal_appeal', "
            "'external_review', 'cms_or_state_complaint')",
            name="ck_appeal_tracks_state",
        ),
        Index("idx_appeal_tracks_case_file_id", "case_file_id"),
    )

    appeal_track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=False
    )
    current_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'call'"))
    # Transition history: [{from, to, at, note}, ...].
    history: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
