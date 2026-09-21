"""The ONE place a reviewer verdict is recorded (deep review C3, 2026-09-18).

Brock's §7-2b rules — a disapproval names a type, a scope, exactly one cause and the
three-prompt structured note — were enforced only by the new review route; the legacy
`POST /admin/cases/{id}/verdict` still wrote bare verdicts and never touched case_reviews, so
those verdicts were invisible to the approval rate. Both routes now call ``record_verdict``:
one validator, one state machine, one audit shape. A structural test asserts nothing else in
the app constructs an AdminVerdict.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.emit import emit
from app.auth import CurrentUser
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CaseReview
from app.db.models.findings import Finding
from app.review import queue as review_queue
from app.review.routing import CAUSES, route_verdict
from app.routes.admin._deps import audit_admin_action

log = structlog.get_logger()

# Disapproval types: the existing verdict enum minus unable_to_verify (that is the
# Can't-verify action) and minus correct (that is the Approve action).
DISAPPROVAL_TYPES = ("partially_correct", "wrong", "missed_finding", "hallucinated", "partial")
_NOTE_KEYS = ("concluded", "should_have_concluded", "input_or_rule")


@dataclass
class VerdictInput:
    action: str  # approve | disapprove | cant_verify
    note: str | None = None
    verdict_type: str | None = None
    scope: str | None = None  # whole_case | findings
    target_findings: list[str] | None = None
    cause: str | None = None
    structured_note: dict | None = None
    # CO-9 extras a legacy client may still send — preserved on the row, never required.
    missed_findings: list[str] | None = None
    hallucinated_claims: list[str] | None = None
    target_response: str | None = None


class VerdictRejected(Exception):
    """The verdict failed §7-2b validation; ``problems`` lists everything missing at once."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def action_for_legacy_verdict(verdict: str) -> tuple[str, str | None]:
    """Map the legacy single-field vocabulary onto (action, verdict_type)."""
    if verdict == "correct":
        return "approve", None
    if verdict == "unable_to_verify":
        return "cant_verify", None
    return "disapprove", verdict


def validate_disapproval(v: VerdictInput, case_finding_ids: set[str]) -> list[str]:
    problems: list[str] = []
    if v.verdict_type not in DISAPPROVAL_TYPES:
        problems.append(f"verdict_type must be one of {list(DISAPPROVAL_TYPES)}")
    if v.scope not in ("whole_case", "findings"):
        problems.append("scope is required (whole_case | findings)")
    elif v.scope == "findings":
        targets = [t for t in (v.target_findings or []) if t]
        if not targets:
            problems.append("scope=findings needs at least one target finding")
        elif unknown := [t for t in targets if t not in case_finding_ids]:
            problems.append(f"target_findings not on this case: {unknown}")
    if v.cause not in CAUSES:
        problems.append(f"cause must be exactly one of {list(CAUSES)}")
    sn = v.structured_note
    if not isinstance(sn, dict):
        problems.append(
            "structured_note is required (concluded / should_have_concluded / input_or_rule)"
        )
    else:
        for k in _NOTE_KEYS:
            if not str(sn.get(k) or "").strip():
                problems.append(f"structured_note.{k} must not be empty")
    return problems


async def record_verdict(
    session: AsyncSession, *, admin: CurrentUser, cf: CaseFile, v: VerdictInput, via: str
) -> dict[str, Any]:
    """Validate, append the verdict row, move the review row, audit, commit, emit. ``via`` names
    the route for the audit trail (review | legacy_cases_route). Raises VerdictRejected."""
    finding_ids = {
        str(x)
        for x in (
            await session.execute(
                select(Finding.finding_id).where(Finding.case_file_id == cf.case_file_id)
            )
        )
        .scalars()
        .all()
    }
    now = datetime.datetime.now(datetime.timezone.utc)
    if v.action == "approve":
        verdict_type, state, targets, cause, sn = "correct", "approved", None, None, None
    elif v.action == "cant_verify":
        verdict_type, state, targets, cause, sn = (
            "unable_to_verify",
            "cant_verify",
            None,
            None,
            None,
        )
    elif v.action == "disapprove":
        problems = validate_disapproval(v, finding_ids)
        if problems:
            raise VerdictRejected(problems)
        verdict_type, state = str(v.verdict_type), "disapproved"
        targets = list(v.target_findings or []) if v.scope == "findings" else None
        cause = v.cause
        sn = {k: str((v.structured_note or {}).get(k) or "").strip() for k in _NOTE_KEYS}
    else:
        raise VerdictRejected([f"unknown action {v.action!r} (approve | disapprove | cant_verify)"])

    verdict = AdminVerdict(
        admin_user_id=admin.user_id,
        case_file_id=cf.case_file_id,
        verdict=verdict_type,
        notes=(v.note or "").strip() or None,
        target_findings=targets,
        target_response=v.target_response,
        missed_findings=v.missed_findings,
        hallucinated_claims=v.hallucinated_claims,
        cause=cause,
        structured_note=sn,
    )
    session.add(verdict)
    await session.flush()

    review = await review_queue.latest_review(session, cf.case_file_id)
    if review is None or review.state in review_queue.DECIDED_STATES:
        # A verdict on a run the policy skipped (or a second verdict on a decided run) still
        # gets its own row — append-only, linked to its predecessor.
        review = CaseReview(
            case_file_id=cf.case_file_id,
            run_seq=(review.run_seq + 1) if review else 1,
            prior_review_id=review.review_id if review else None,
            terminal_status=cf.status,
            incomplete_reason=cf.audit_incomplete_reason,
            findings_count=len(finding_ids),
            enqueued_at=now,
            documents_fingerprint=review_queue.documents_fingerprint(cf.documents),
        )
        session.add(review)
    review.state = state
    review.reviewer_id = admin.user_id
    review.decided_at = now
    review.verdict_id = verdict.verdict_id
    if review.in_review_at is None:
        review.in_review_at = now

    scope = v.scope if v.action == "disapprove" else "whole_case"
    await audit_admin_action(
        session,
        admin=admin,
        action="review_verdict",
        target_user_id=cf.user_id,
        case_file_id=cf.case_file_id,
        extra={
            "review_id": str(review.review_id),
            "verdict_id": str(verdict.verdict_id),
            "review_action": v.action,
            "verdict": verdict_type,
            "cause": cause,
            "scope": scope,
            "via": via,
        },
    )
    await session.commit()
    await emit(
        "review_verdict_recorded",
        user_id=admin.user_id,
        case_file_id=cf.case_file_id,
        properties={
            "action": v.action,
            "cause": cause or "none",
            "scope": scope,
            "findings_in_scope": len(targets or []),
        },
    )
    target = route_verdict(cause=cause)
    log.info(
        "review.verdict.recorded",
        case_file_id=str(cf.case_file_id),
        review_id=str(review.review_id),
        state=state,
        cause=cause,
        via=via,
        phase2_route=target.value if target else None,
    )
    return {
        "review_id": str(review.review_id),
        "state": state,
        "verdict_id": str(verdict.verdict_id),
        "verdict": verdict_type,
        "cause": cause,
        "phase2_route": target.value if target else None,
    }
