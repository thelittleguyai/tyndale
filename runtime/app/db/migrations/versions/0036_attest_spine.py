"""attest-and-proceed spine (Brock July 16 §A2 state 1; first brick of the D2 attest spine)

- case_files.patient_name: TYPED extracted patient/member name (DL-39 — the mismatch trigger
  compares typed fields, never prose).
- case_files.attest_status: not_required | required | attested | declined — the gate the
  encounter-verification endpoint enforces.
- case status gains 'attest_declined' (graceful close on "I'm not authorized"; no audit).
- messages kind gains 'attest_request' (the relationship-menu thread entry).
- audit_events event_type gains 'attestation' (every attest/decline persists through the
  encrypted envelope) and 'access_request' (§12 deletion/access intake stub — same
  constraint churn, one migration).

Chains onto 0035.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

_STATUS_NEW = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'awaiting_eob_confirmation', 'audit_running', "
    "'audit_complete', 'audit_incomplete', 'extraction_failed', 'not_a_bill', "
    "'resolved', 'archived', 'attest_declined')"
)
_STATUS_OLD = (
    "status IN ('open', 'in_progress', 'encounter_verification_pending', "
    "'encounter_verified', 'awaiting_eob_confirmation', 'audit_running', "
    "'audit_complete', 'audit_incomplete', 'extraction_failed', 'not_a_bill', "
    "'resolved', 'archived')"
)
_KIND_NEW = (
    "kind IN ('message', 'status_card_update', 'system_message', 'moment_card', "
    "'verification_request', 'verification_suggestion', 'attest_request')"
)
_KIND_OLD = (
    "kind IN ('message', 'status_card_update', 'system_message', 'moment_card', "
    "'verification_request', 'verification_suggestion')"
)
_EVENT_NEW = (
    "event_type IN ('tool_invocation', 'subagent_call', 'model_call', "
    "'user_action', 'system_action', 'hook_invocation', 'phi_block', "
    "'attestation', 'access_request')"
)
_EVENT_OLD = (
    "event_type IN ('tool_invocation', 'subagent_call', 'model_call', "
    "'user_action', 'system_action', 'hook_invocation', 'phi_block')"
)


def upgrade() -> None:
    op.add_column("case_files", sa.Column("patient_name", sa.Text(), nullable=True))
    op.add_column(
        "case_files",
        sa.Column("attest_status", sa.Text(), nullable=False, server_default="not_required"),
    )
    op.create_check_constraint(
        "ck_case_files_attest_status",
        "case_files",
        "attest_status IN ('not_required', 'required', 'attested', 'declined')",
    )
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _STATUS_NEW)
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.create_check_constraint("ck_messages_kind", "messages", _KIND_NEW)
    op.drop_constraint("ck_audit_events_event_type", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_events_event_type", "audit_events", _EVENT_NEW)


def downgrade() -> None:
    op.execute("UPDATE case_files SET status = 'archived' WHERE status = 'attest_declined'")
    op.execute("UPDATE messages SET kind = 'system_message' WHERE kind = 'attest_request'")
    op.execute(
        "UPDATE audit_events SET event_type = 'user_action' "
        "WHERE event_type IN ('attestation', 'access_request')"
    )
    op.drop_constraint("ck_audit_events_event_type", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_events_event_type", "audit_events", _EVENT_OLD)
    op.drop_constraint("ck_messages_kind", "messages", type_="check")
    op.create_check_constraint("ck_messages_kind", "messages", _KIND_OLD)
    op.drop_constraint("ck_case_files_status", "case_files", type_="check")
    op.create_check_constraint("ck_case_files_status", "case_files", _STATUS_OLD)
    op.drop_constraint("ck_case_files_attest_status", "case_files", type_="check")
    op.drop_column("case_files", "attest_status")
    op.drop_column("case_files", "patient_name")
