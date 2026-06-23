"""PlanLibrary — plan-level benefit designs (Phase CO-12C, DL-73).

PLAN-LEVEL ONLY, NO PHI: an entry is keyed by (payer, plan_id/name, plan_year) and
holds benefit terms (deductible / coinsurance / OOP / copays) in ``benefit_design``.
Every user identifier is stripped before write (app/services/plan_library.py
::strip_identifiers — an allowlist). The library is keyed by a plan, never a person.

``confidence`` counts corroborating user confirmations; a reject FORKS a new entry
rather than overwriting (so competing designs coexist, ranked by confidence).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlanLibraryEntry(Base):
    __tablename__ = "plan_library"
    __table_args__ = (Index("idx_plan_library_match", "payer", "plan_year"),)

    plan_library_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    payer: Mapped[str] = mapped_column(Text, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Benefit terms ONLY — no identifiers (strip_identifiers gates writes).
    benefit_design: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Corroborating confirmations (a confirm increments; a reject forks a new row).
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'user_confirmed'")
    )  # user_confirmed | public_qhp (later)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
