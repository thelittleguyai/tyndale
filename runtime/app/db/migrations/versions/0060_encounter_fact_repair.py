"""Repair the cases a second translate read corrupted — e2e round 3, R1.

Before the fact registry (app/agents/encounter_facts.py) the thread screen's POST /extract on
every mount re-translated a case's bill and APPENDED re-worded copies of every charge under fresh
line_item_ids — on a finished audit too: dev specimen 36736626 went audit_complete →
encounter_verification_pending; dc0ed582 had the copies appended while its audit ran. This
migration repairs such rows once:

  * a line item nobody answered, on a case whose answers were already submitted, whose code is
    the code of an ANSWERED item, is a copy a later read appended — every submit before this
    change answered every item then on the case. It is dropped. An unanswered item with a code
    of its own is a charge a new document brought; it stays, to be asked.
  * a case left in encounter_verification_pending with every remaining item answered, whose
    audit had reached a terminal state (its lifecycle event is on record), goes back to the
    latest terminal state recorded.

The code normalization is a FROZEN copy of encounter_facts.normalize_code (a migration must not
import app code that can move). Idempotent. Downgrade is a no-op: the dropped rows were copies.
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

_CODE_JOIN = re.compile(r"[^A-Z0-9]+")
# lifecycle event (orchestrator._emit_lifecycle_event) → the terminal it recorded
TERMINAL_EVENTS = {
    "audit_completed": ("audit_complete", None),
    "audit_needs_documents": ("audit_incomplete", "needs_documents"),
    "audit_system_error": ("audit_incomplete", "system_error"),
}


def _code(value) -> str:
    return _CODE_JOIN.sub("-", str(value or "").upper()).strip("-")


def repair(conn) -> tuple[int, int]:
    """(cases whose appended copies were dropped, cases returned to their terminal state)."""
    rows = conn.execute(
        sa.text(
            "SELECT case_file_id, status, line_items, encounter_confirmations FROM case_files "
            "WHERE jsonb_typeof(encounter_confirmations) = 'array' "
            "AND jsonb_array_length(encounter_confirmations) > 0"
        ).columns(
            sa.column("case_file_id", postgresql.UUID(as_uuid=True)),
            sa.column("status", sa.Text()),
            sa.column("line_items", postgresql.JSONB()),
            sa.column("encounter_confirmations", postgresql.JSONB()),
        )
    ).mappings().all()
    set_items = sa.text(
        "UPDATE case_files SET line_items = :items WHERE case_file_id = :cid"
    ).bindparams(sa.bindparam("items", type_=postgresql.JSONB))
    latest_terminal = sa.text(
        "SELECT event_name FROM analytics_events WHERE case_file_id = :cid "
        "AND event_name IN ('audit_completed', 'audit_needs_documents', 'audit_system_error') "
        "ORDER BY occurred_at DESC LIMIT 1"
    )
    set_status = sa.text(
        "UPDATE case_files SET status = :status, audit_incomplete_reason = :reason "
        "WHERE case_file_id = :cid AND status = 'encounter_verification_pending'"
    )
    items_fixed = status_fixed = 0
    for row in rows:
        items = [i for i in (row["line_items"] or []) if isinstance(i, dict)]
        answered = {
            c.get("line_item_id") for c in row["encounter_confirmations"] if isinstance(c, dict)
        }
        answered_codes = {_code(i.get("code")) for i in items if i.get("line_item_id") in answered}
        kept = [
            i for i in items
            if i.get("line_item_id") in answered or _code(i.get("code")) not in answered_codes
        ]
        if len(kept) != len(items):
            conn.execute(set_items, {"items": kept, "cid": row["case_file_id"]})
            items_fixed += 1
        if (
            row["status"] == "encounter_verification_pending"
            and kept
            and all(i.get("line_item_id") in answered for i in kept)
        ):
            event = conn.execute(latest_terminal, {"cid": row["case_file_id"]}).scalar()
            if event in TERMINAL_EVENTS:
                status, reason = TERMINAL_EVENTS[event]
                conn.execute(set_status, {"status": status, "reason": reason, "cid": row["case_file_id"]})
                status_fixed += 1
    return items_fixed, status_fixed


def upgrade() -> None:
    repair(op.get_bind())


def downgrade() -> None:
    pass  # the dropped rows were copies of answered facts; nothing to restore
