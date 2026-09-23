"""Human Review, Phase 1 (doc 39 §1–§2 as amended by §7 — Brock 2026-09-17).

One row per CASE RUN in the review queue. States: unreviewed → in_review → approved |
disapproved | cant_verify; ``re_review`` is set automatically when a case re-runs after its
documents change — the prior row (and its verdict) is KEPT and linked via prior_review_id,
never overwritten. The enqueue facts (why this run entered the queue, its confidence band,
the tripwire flags) are stamped at enqueue time so the queue filters read columns instead of
re-deriving an audit per row.

``admin_settings`` is the tiny durable key/value store behind the admin-settable dials
(review_sample_pct) — env gives the default, an admin PUT overrides it, restarts keep it.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

REVIEW_STATES = ("unreviewed", "in_review", "approved", "disapproved", "cant_verify", "re_review")
CONFIDENCE_BANDS = ("high", "medium", "low", "unknown")


class CaseReview(Base):
    __tablename__ = "case_reviews"
    __table_args__ = (
        CheckConstraint(
            "state IN ('unreviewed', 'in_review', 'approved', 'disapproved', 'cant_verify', "
            "'re_review')",
            name="ck_case_reviews_state",
        ),
        CheckConstraint(
            "confidence_band IN ('high', 'medium', 'low', 'unknown')",
            name="ck_case_reviews_confidence_band",
        ),
        # One row per case RUN — two concurrent terminal transitions must not both insert it.
        UniqueConstraint("case_file_id", "run_seq", name="uq_case_reviews_case_run"),
        Index("idx_case_reviews_case_file", "case_file_id"),
        Index("idx_case_reviews_state_enqueued", "state", "enqueued_at"),
        Index("idx_case_reviews_decided_at", "decided_at"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_files.case_file_id"), nullable=False
    )
    run_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unreviewed'"))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    verdict_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_verdicts.verdict_id"), nullable=True
    )
    prior_review_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_reviews.review_id"), nullable=True
    )
    # Enqueue facts — stamped once, read by the queue filters + health strip.
    terminal_status: Mapped[str] = mapped_column(Text, nullable=False)
    incomplete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_band: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    triggers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    sampled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    first_case: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    system_error: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # M6 (e2e 2026-09-23): `canary_flag` means a PLANTED fixture marker leaked (02417 / 05821 /
    # Z4411) — the meaning "canary" always had. `guard_drop_flag` means a fabrication guard
    # removed or downgraded something on a legitimate run. Until now the one column meant both.
    canary_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    guard_drop_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    material_disagreement: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Digest of the document inventory at enqueue — a later run with a different digest is
    # "a re-run after document change" (re_review, forced regardless of the dial).
    documents_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    net_finding_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    enqueued_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    in_review_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    decided_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
