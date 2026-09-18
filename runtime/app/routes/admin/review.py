"""Human Review Phase 1 — the reviewer queue + workspace + verdicts (doc 39 §1–§2 as
amended by §7, Brock 2026-09-17; built 2026-09-18).

Admin only (DL-60: non-admin → 404). Every workspace VIEW writes an audit-log event; every
verdict is append-only with the reviewer's UUID as actor. The queue policy itself lives in
app.review.queue (hooked from the orchestrator's status chokepoint) — these routes only read
rows and record decisions.

The workspace assembles its four tabs from EXISTING data only. Anything Phase 2 will add
(API pulls, live lookups, Missing / Retrieval-misses) is returned as a labeled placeholder,
never faked.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CONFIDENCE_BANDS, REVIEW_STATES, CaseReview
from app.db.session import get_session
from app.review import queue as review_queue
from app.routes.admin._deps import admin_user, audit_admin_action
from app.routes.admin._deps import iso as _iso

log = structlog.get_logger()
router = APIRouter(tags=["v1-admin"])

# Disapproval types: the existing verdict enum minus unable_to_verify (that is the
# Can't-verify action) and minus correct (that is the Approve action).
DISAPPROVAL_TYPES = ("partially_correct", "wrong", "missed_finding", "hallucinated", "partial")
_PHASE2_PLACEHOLDER = {"status": "coming_in_phase_2", "label": "Coming in Phase 2"}
_DOC_TEXT_KEYS = ("ocr_text", "full_text", "text_preview", "preview", "text")


def _mask(uid: uuid.UUID | str | None) -> str | None:
    """Masked user id for the queue (mockup: `u·8c41`) — never an email on the list page."""
    return f"u·{str(uid)[-4:]}" if uid else None


def _age_hours(t: datetime.datetime | None, now: datetime.datetime) -> float | None:
    if t is None:
        return None
    return round(max(0.0, (now - t).total_seconds() / 3600.0), 1)


def _review_dict(
    r: CaseReview,
    *,
    now: datetime.datetime,
    verdict: AdminVerdict | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return {
        "review_id": str(r.review_id),
        "case_file_id": str(r.case_file_id),
        "user_masked": _mask(user_id),
        "run_seq": r.run_seq,
        "state": r.state,
        "terminal_status": r.terminal_status,
        "incomplete_reason": r.incomplete_reason,
        "confidence_band": r.confidence_band,
        "findings_count": r.findings_count,
        "net_finding_usd": float(r.net_finding_usd) if r.net_finding_usd is not None else None,
        "sampled": r.sampled,
        "triggers": list(r.triggers or []),
        "flags": {
            "first_case": r.first_case,
            "system_error": r.system_error,
            "canary": r.canary_flag,
            "material_disagreement": r.material_disagreement,
        },
        "enqueued_at": _iso(r.enqueued_at),
        "age_hours": _age_hours(r.enqueued_at, now),
        "in_review_at": _iso(r.in_review_at),
        "decided_at": _iso(r.decided_at),
        "reviewer_masked": _mask(r.reviewer_id),
        "prior_review_id": str(r.prior_review_id) if r.prior_review_id else None,
        "verdict": (
            {"verdict_id": str(verdict.verdict_id), "verdict": verdict.verdict, "cause": None}
            if verdict is not None
            else None
        ),
    }


def _verdict_dict(v: AdminVerdict) -> dict[str, Any]:
    return {
        "verdict_id": str(v.verdict_id),
        "verdict": v.verdict,
        "notes": v.notes,
        "cause": v.cause,
        "structured_note": v.structured_note,
        "target_findings": v.target_findings,
        "target_response": v.target_response,
        "missed_findings": v.missed_findings,
        "hallucinated_claims": v.hallucinated_claims,
        "reviewer_masked": _mask(v.admin_user_id),
        "captured_at": _iso(v.captured_at),
    }


# ── queue ───────────────────────────────────────────────────────────────────────────────


@router.get("/admin/review/queue")
async def review_queue_list(
    state: str | None = Query(None, description="comma-separated review states"),
    verdict: str | None = Query(None, description="verdict type of decided rows"),
    confidence: str | None = Query(None, description="comma-separated bands"),
    has_system_error: bool | None = Query(None),
    canary: bool | None = Query(None),
    since: datetime.datetime | None = Query(None, description="enqueued_at >= (ISO)"),
    until: datetime.datetime | None = Query(None, description="enqueued_at < (ISO)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The reviewer queue. Default order: pending rows first (unreviewed / re_review / in_review),
    oldest enqueued first — the mockup's 'oldest unreviewed at the top'."""
    now = datetime.datetime.now(datetime.timezone.utc)
    q = (
        select(CaseReview, AdminVerdict, CaseFile.user_id)
        .join(CaseFile, CaseFile.case_file_id == CaseReview.case_file_id)
        .outerjoin(AdminVerdict, AdminVerdict.verdict_id == CaseReview.verdict_id)
    )
    if state:
        states = [s.strip() for s in state.split(",") if s.strip()]
        bad = [s for s in states if s not in REVIEW_STATES]
        if bad:
            raise HTTPException(status_code=422, detail=f"unknown review state(s): {bad}")
        q = q.where(CaseReview.state.in_(states))
    if verdict:
        q = q.where(AdminVerdict.verdict == verdict)
    if confidence:
        bands = [b.strip() for b in confidence.split(",") if b.strip()]
        bad = [b for b in bands if b not in CONFIDENCE_BANDS]
        if bad:
            raise HTTPException(status_code=422, detail=f"unknown confidence band(s): {bad}")
        q = q.where(CaseReview.confidence_band.in_(bands))
    if has_system_error is not None:
        q = q.where(CaseReview.system_error.is_(has_system_error))
    if canary is not None:
        q = q.where(CaseReview.canary_flag.is_(canary))
    if since is not None:
        q = q.where(CaseReview.enqueued_at >= since)
    if until is not None:
        q = q.where(CaseReview.enqueued_at < until)
    pending_first = case((CaseReview.state.in_(review_queue.PENDING_STATES), 0), else_=1)
    rows = (
        await session.execute(
            q.order_by(pending_first, CaseReview.enqueued_at.asc()).limit(limit).offset(offset)
        )
    ).all()
    items = [_review_dict(r, now=now, verdict=v, user_id=uid) for r, v, uid in rows]
    return {
        "items": items,
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "health": await review_queue.health(session, now=now),
    }


# ── settings (the dial) ──────────────────────────────────────────────────────────────────


class ReviewSettingsRequest(BaseModel):
    review_sample_pct: int = Field(ge=0, le=100)


@router.get("/admin/review/settings")
async def review_settings(
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    from app.config import get_settings

    s = get_settings()
    return {
        "review_sample_pct": await review_queue.effective_sample_pct(session),
        "env_default_pct": s.review_sample_pct,
        "triggers": {
            "first_case": s.review_trigger_first_case,
            "low_confidence": s.review_trigger_low_confidence,
            "system_error": s.review_trigger_system_error,
            "canary": s.review_trigger_canary,
            "material_disagreement": s.review_trigger_material_disagreement,
        },
    }


@router.put("/admin/review/settings")
async def update_review_settings(
    body: ReviewSettingsRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    pct = await review_queue.set_sample_pct(session, body.review_sample_pct, admin_id=admin.user_id)
    await audit_admin_action(
        session, admin=admin, action="review_settings", extra={"review_sample_pct": pct}
    )
    await session.commit()
    return {"review_sample_pct": pct}
