"""AuditEvent model — matches docs/integration-contracts.md Section 2.2.

Phase 1C note: `payload_encrypted` holds CLEAR-TEXT JSON bytes as a placeholder.
TODO(Phase 4): the security/HIPAA spine replaces this with AES-GCM ciphertext keyed
from Azure Key Vault, and sets a real `key_version`.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import TIMESTAMP, CheckConstraint, Index, Integer, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('tool_invocation', 'subagent_call', 'model_call', "
            "'user_action', 'system_action', 'hook_invocation', 'phi_block')",
            name="ck_audit_events_event_type",
        ),
        CheckConstraint(
            "outcome IN ('success', 'error', 'timeout', 'blocked')",
            name="ck_audit_events_outcome",
        ),
        Index("idx_audit_events_case_file", "case_file_id"),
        Index("idx_audit_events_user", "user_id"),
        Index("idx_audit_events_timestamp", "timestamp"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)  # subagent | user_id | system_process
    case_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # AES-GCM ciphertext in prod; clear-text JSON bytes in Phase 1C (see module docstring).
    payload_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # SHA-256
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 placeholder in Phase 1C
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_chunks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tools_invoked: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)  # scrubbed; null on success
