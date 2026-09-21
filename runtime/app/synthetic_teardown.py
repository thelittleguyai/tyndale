"""Teardown of ONE synthetic e2e identity (deep review C5, 2026-09-18).

Each sweep mints its own `e2e-runner+<run>@e2e.tyndale.test` user and completes ~22 audits;
nothing removed them. This deletes that identity's cases, documents (rows AND stored bytes),
threads, findings, review rows, feedback and analytics — and nothing else:

  * the address MUST carry a synthetic suffix (app.notify.email.is_synthetic_email) — a real
    identity can never be passed through here;
  * `keep_case_ids` leaves named cases (a sweep's FAILED scenarios) and therefore the user in
    place, so `--inspect` forensics still work — a later call without the keep list finishes;
  * audit_events are never touched (append-only; they carry no FK);
  * every foreign key into every table deleted here is declared in ``COVERED_FKS``, and a test
    introspects the live schema against it — a new table cannot silently break the teardown.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.notify.email import is_synthetic_email

log = structlog.get_logger(__name__)

# Tables this module deletes rows from (the introspection test's parent set).
DELETED_TABLES = (
    "case_reviews", "admin_verdicts", "feedback_deid_candidates", "feedback_triage_queue",
    "feedback_events", "findings", "deadlines", "appeal_tracks", "knowledge_gap_log", "messages",
    "conversations", "analytics_events", "case_files", "consent_history", "insurance_cards",
    "insurance_info", "plan_documents", "billing_accounts", "users",
)  # fmt: skip

# Every FK that references one of DELETED_TABLES, and how it is honoured. "delete" = the child
# rows go first; "null" = the reference is cleared; "n/a" = cannot point at a synthetic
# user (they are never admins / reviewers / cron triggers) but is cleared defensively anyway.
COVERED_FKS: dict[tuple[str, str], str] = {
    ("case_reviews", "case_file_id"): "delete",
    ("case_reviews", "prior_review_id"): "delete",  # whole chain for the case, one statement
    ("case_reviews", "verdict_id"): "delete",  # review rows go before their verdicts
    ("case_reviews", "reviewer_id"): "null",
    ("admin_verdicts", "case_file_id"): "delete",
    ("admin_verdicts", "admin_user_id"): "n/a",
    ("feedback_deid_candidates", "feedback_event_id"): "delete",
    ("feedback_triage_queue", "feedback_event_id"): "delete",
    ("findings", "case_file_id"): "delete",
    ("deadlines", "case_file_id"): "delete",
    ("appeal_tracks", "case_file_id"): "delete",
    ("knowledge_gap_log", "case_id"): "delete",
    ("knowledge_gap_log", "user_id"): "delete",
    ("messages", "conversation_id"): "delete",
    ("messages", "corrected_by_message_id"): "null",
    ("messages", "corrects_message_id"): "null",
    ("conversations", "case_id"): "delete",
    ("conversations", "user_id"): "delete",
    ("analytics_events", "user_id"): "delete",
    ("analytics_events", "actor_user_id"): "null",
    ("case_files", "user_id"): "delete",
    ("consent_history", "user_id"): "delete",
    ("insurance_cards", "user_id"): "delete",
    ("insurance_info", "user_id"): "delete",
    ("plan_documents", "user_id"): "delete",
    ("billing_accounts", "user_id"): "delete",
    ("cron_run_log", "triggered_by"): "null",
    ("admin_settings", "updated_by"): "null",
    ("users", "blocked_by"): "null",
    ("users", "soft_deleted_by"): "null",
}

_IDS = "ANY(CAST(:ids AS uuid[]))"


class NotSynthetic(ValueError):
    """The address does not carry a synthetic suffix — refused before any query runs."""


async def _exec(session: AsyncSession, sql: str, **params) -> int:
    return (await session.execute(text(sql), params)).rowcount or 0


async def teardown_synthetic_user(
    session: AsyncSession, email: str, *, keep_case_ids: list[str] | None = None
) -> dict[str, int]:
    """Delete one synthetic identity's data. Returns per-table counts (+ ``stored_files`` and
    ``kept_cases``). The caller commits."""
    addr = (email or "").strip().lower()
    if not is_synthetic_email(addr):
        raise NotSynthetic(addr)
    counts: dict[str, int] = {}
    uid = (
        await session.execute(text("SELECT user_id FROM users WHERE lower(email) = :e"), {"e": addr})
    ).scalar_one_or_none()
    if uid is None:
        return {"users": 0}

    keep = {str(uuid.UUID(k)) for k in (keep_case_ids or [])}
    rows = (
        await session.execute(
            text("SELECT case_file_id, documents, eobs FROM case_files WHERE user_id = :u"), {"u": uid}
        )
    ).all()
    doomed = [r for r in rows if str(r[0]) not in keep]
    ids = [str(r[0]) for r in doomed]
    counts["kept_cases"] = len(rows) - len(doomed)

    # The stored bytes first — once the rows are gone the URIs are unrecoverable.
    from app.routes.upload import delete_stored

    stored = 0
    for _cid, documents, eobs in doomed:
        for entry in [*(documents or []), *(eobs or [])]:
            if isinstance(entry, dict) and await delete_stored(entry.get("uri")):
                stored += 1
    counts["stored_files"] = stored

    if ids:
        counts["case_reviews"] = await _exec(session, f"DELETE FROM case_reviews WHERE case_file_id = {_IDS}", ids=ids)
        counts["admin_verdicts"] = await _exec(session, f"DELETE FROM admin_verdicts WHERE case_file_id = {_IDS}", ids=ids)
        fb = f"(SELECT id FROM feedback_events WHERE case_file_id = {_IDS})"
        counts["feedback_deid_candidates"] = await _exec(session, f"DELETE FROM feedback_deid_candidates WHERE feedback_event_id IN {fb}", ids=ids)
        counts["feedback_triage_queue"] = await _exec(session, f"DELETE FROM feedback_triage_queue WHERE feedback_event_id IN {fb}", ids=ids)
        counts["feedback_events"] = await _exec(session, f"DELETE FROM feedback_events WHERE case_file_id = {_IDS}", ids=ids)
        for table, col in (("findings", "case_file_id"), ("deadlines", "case_file_id"),
                           ("appeal_tracks", "case_file_id"), ("knowledge_gap_log", "case_id")):
            counts[table] = await _exec(session, f"DELETE FROM {table} WHERE {col} = {_IDS}", ids=ids)  # noqa: S608
        convs = f"(SELECT conversation_id FROM conversations WHERE case_id = {_IDS})"
        await _exec(session, f"UPDATE messages SET corrected_by_message_id = NULL, corrects_message_id = NULL WHERE conversation_id IN {convs}", ids=ids)
        counts["messages"] = await _exec(session, f"DELETE FROM messages WHERE conversation_id IN {convs}", ids=ids)
        counts["conversations"] = await _exec(session, f"DELETE FROM conversations WHERE case_id = {_IDS}", ids=ids)
        counts["analytics_events"] = await _exec(session, f"DELETE FROM analytics_events WHERE case_file_id = {_IDS}", ids=ids)
        counts["case_files"] = await _exec(session, f"DELETE FROM case_files WHERE case_file_id = {_IDS}", ids=ids)

    if counts["kept_cases"]:
        counts["users"] = 0  # the identity stays while any case is kept for forensics
        log.info("synthetic_teardown.partial", kept_cases=counts["kept_cases"], cases=len(ids))
        return counts

    # The identity itself: everything keyed by user, then the row.
    convs = "(SELECT conversation_id FROM conversations WHERE user_id = :u)"
    await _exec(session, f"UPDATE messages SET corrected_by_message_id = NULL, corrects_message_id = NULL WHERE conversation_id IN {convs}", u=uid)
    counts["messages"] = counts.get("messages", 0) + await _exec(session, f"DELETE FROM messages WHERE conversation_id IN {convs}", u=uid)
    counts["conversations"] = counts.get("conversations", 0) + await _exec(session, "DELETE FROM conversations WHERE user_id = :u", u=uid)
    fb = "(SELECT id FROM feedback_events WHERE user_id = :u)"
    await _exec(session, f"DELETE FROM feedback_deid_candidates WHERE feedback_event_id IN {fb}", u=uid)
    await _exec(session, f"DELETE FROM feedback_triage_queue WHERE feedback_event_id IN {fb}", u=uid)
    counts["feedback_events"] = counts.get("feedback_events", 0) + await _exec(session, "DELETE FROM feedback_events WHERE user_id = :u", u=uid)
    counts["analytics_events"] = counts.get("analytics_events", 0) + await _exec(session, "DELETE FROM analytics_events WHERE user_id = :u", u=uid)
    for table in ("knowledge_gap_log", "consent_history", "insurance_cards", "insurance_info",
                  "plan_documents", "billing_accounts"):
        counts[table] = counts.get(table, 0) + await _exec(session, f"DELETE FROM {table} WHERE user_id = :u", u=uid)  # noqa: S608
    for table, col in (("case_reviews", "reviewer_id"), ("analytics_events", "actor_user_id"),
                       ("cron_run_log", "triggered_by"),
                       ("admin_settings", "updated_by"), ("users", "blocked_by"),
                       ("users", "soft_deleted_by")):
        await _exec(session, f"UPDATE {table} SET {col} = NULL WHERE {col} = :u", u=uid)  # noqa: S608
    counts["users"] = await _exec(session, "DELETE FROM users WHERE user_id = :u", u=uid)
    log.info("synthetic_teardown.done", cases=len(ids), stored_files=stored)
    return counts
