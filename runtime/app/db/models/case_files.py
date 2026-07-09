"""CaseFile model — matches docs/integration-contracts.md Section 2.3.

Includes the `research_log` JSONB field (Change Order 001 item 4) and a `version`
column for optimistic locking (enforcement wires into the write paths in Phase 2).
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.plan_types import PLAN_TYPES

# Canonical 14 regimes as a SQL IN-list — single source of truth (app.plan_types).
_REGIME_SQL_IN = ", ".join(f"'{t}'" for t in PLAN_TYPES)


class CaseFile(Base):
    __tablename__ = "case_files"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'encounter_verification_pending', "
            "'encounter_verified', 'awaiting_eob_confirmation', 'audit_running', "
            "'audit_complete', 'audit_incomplete', 'extraction_failed', 'resolved', 'archived')",
            name="ck_case_files_status",
        ),
        CheckConstraint(
            "intake_status IN ('not_started', 'in_progress', 'complete')",
            name="ck_case_files_intake_status",
        ),
        CheckConstraint(
            "audit_incomplete_reason IS NULL OR "
            "audit_incomplete_reason IN ('needs_documents', 'system_error')",
            name="ck_case_files_audit_incomplete_reason",
        ),
        CheckConstraint(
            f"coverage_regime IS NULL OR coverage_regime IN ({_REGIME_SQL_IN})",
            name="ck_case_files_coverage_regime",
        ),
        Index("idx_case_files_intake_status", "intake_status"),
        # Every dashboard / intake / user-scoped query filters on user_id
        # (migration 0019).
        Index("idx_case_files_user_id", "user_id"),
    )

    case_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Documents uploaded for this case (bills, EOBs, insurance card, plan summary).
    documents: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Structured coverage — matches the FHIR Coverage return shape (source-agnostic).
    coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Structured EOB data — same shape as fhir_get_eobs return.
    eobs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Lead Planner plan-to-memory (current plan + version history).
    plan_current: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    plan_history: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # research_log per Change Order 001 item 4. Each entry:
    # {timestamp, topic, what_was_checked, result_summary, finding_id|null}
    research_log: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Phase 2I encounter verification — Bill Detective's plain-language line-item
    # translations (each a LineItem dict; see app/schemas/encounter.py).
    line_items: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # The user's per-line-item confirmations (each a LineItemConfirmation dict).
    encounter_confirmations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Phase 2J — set when the user answers/skips an outcome follow-up prompt,
    # so the dashboard stops re-prompting. NULL = never prompted/answered.
    last_outcome_check_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Optimistic locking counter.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # Phase CO-1A guided intake. intake_status gates the wizard (new users land in
    # it; 'complete' users go straight to the dashboard). intake_current_step is the
    # wizard step name to resume at. visit_context is the free-text "what were you
    # seen for?" answer (DL-54: no CPT codes echoed back to the user).
    intake_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'not_started'")
    )
    intake_current_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    visit_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sprint B (DL-82): the case's coverage regime + detection metadata
    # (method/confidence/evidence/verified). The audit orchestrator reads
    # coverage_regime to route + tag findings' provenance; null/unconfirmed →
    # audited under generic rules with an explicit assumption. Never guessed.
    coverage_regime: Mapped[str | None] = mapped_column(Text, nullable=True)
    regime_detection: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Brock 2026-07-06 — typed coverage attributes (qmb_status, medigap, dsnp, grandfathered, …)
    # validated against the regime by app.plan_types. NOT buckets; a nullable value = the
    # attribute is unknown (the flagship QMB never-bill check keys on qmb_status IS TRUE only).
    coverage_attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Sprint G: nudge stages already sent for this case's load-bearing data-fetch items
    # (e.g. ["+3d", "+14d"]) — the idempotency ledger so a stage never double-sends.
    nudges_sent: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Why an audit_incomplete case stopped, persisted so GET /v1/audit/{id} can render the honest
    # terminal screen: 'needs_documents' (user-actionable — findings produced, three-number
    # blocked on missing inputs) | 'system_error' (budget/citation/provider). NULL otherwise.
    audit_incomplete_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
