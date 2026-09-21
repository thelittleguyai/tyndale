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
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CONFIDENCE_BANDS, REVIEW_STATES, CaseReview
from app.db.models.conversations import Conversation
from app.db.models.deadlines import Deadline
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.db.models.messages import Message
from app.db.session import get_session
from app.review import queue as review_queue
from app.review.verdicts import DISAPPROVAL_TYPES, VerdictInput, VerdictRejected, record_verdict  # noqa: F401
from app.routes.admin._deps import admin_user, audit_admin_action
from app.routes.admin._deps import iso as _iso
from app.routes.admin.cases import _finding_dict, _load_case, case_provenance
from app.schemas.case_file import as_dict

log = structlog.get_logger()
router = APIRouter(tags=["v1-admin"])

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
            {
                "verdict_id": str(verdict.verdict_id),
                "verdict": verdict.verdict,
                "cause": verdict.cause,
            }
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


# ── workspace ────────────────────────────────────────────────────────────────────────────


def _codes_in(obj: Any) -> list[str]:
    """Code-like strings a finding's facts already name (BASIS codes) — collected from the
    keys the agents write today; nothing is inferred."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("code", "cpt", "cpt_code", "hcpcs", "procedure_code") and isinstance(v, str):
                out.append(v)
            elif k in ("codes", "reference_codes", "cpt_codes", "basis_codes") and isinstance(
                v, list
            ):
                out.extend(str(x) for x in v if isinstance(x, (str, int)))
            elif isinstance(v, (dict, list)):
                out.extend(_codes_in(v))
    elif isinstance(obj, list):
        for x in obj:
            out.extend(_codes_in(x))
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def _first_str(d: dict, *keys: str) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _why_lines(f: Finding) -> list[dict[str, Any]]:
    """The per-finding 'why' expander: five lines, each read from a field the agents already
    persist. A missing field is null — the console renders 'not recorded'. Never synthesized."""
    facts = as_dict(f.facts) or {}
    claim = as_dict(f.legal_claim) or {}
    rec = as_dict(f.recommendation) or {}
    numbers = {
        k: facts[k]
        for k in ("billed_amount", "allowed_amount", "eob_member_responsibility", "computed", "gap")
        if isinstance(facts.get(k), (int, float))
    }
    return [
        {
            "key": "observed",
            "label": "What the documents show",
            "value": _first_str(facts, "notes", "observation", "description", "evidence"),
        },
        {
            "key": "rule",
            "label": "Rule applied",
            "value": _first_str(claim, "claim", "rule", "text"),
        },
        {"key": "numbers", "label": "Numbers compared", "value": numbers or None},
        {
            "key": "action",
            "label": "Recommended action",
            "value": _first_str(rec, "action", "reasoning"),
        },
        {
            "key": "producer",
            "label": "Produced by",
            "value": f"{f.subagent_source} · tier {f.voice_tier}" if f.subagent_source else None,
        },
    ]


def _citations_of(f: Finding) -> list[dict]:
    from app.agents.orchestrator import _project_citations

    claim = as_dict(f.legal_claim) or {}
    raw = claim.get("citations") or claim.get("citation") or []
    try:
        return [c.model_dump() for c in _project_citations(raw)]
    except Exception:  # noqa: BLE001 — a malformed citation renders as none, not a 500
        return []


def _analysis_finding(f: Finding) -> dict[str, Any]:
    facts = as_dict(f.facts) or {}
    d = _finding_dict(f)
    d.update(
        {
            "responsible_party": facts.get("responsible_party") or "either",
            "amount_usd": facts.get("gap") if isinstance(facts.get("gap"), (int, float)) else None,
            "basis_codes": _codes_in(facts),
            "citations": _citations_of(f),
            "confidence": facts.get("confidence")
            if isinstance(facts.get("confidence"), (int, float, str))
            else None,
            "why": _why_lines(f),
            "created_at": _iso(f.created_at),
        }
    )
    return d


def _document_card(i: int, d: dict) -> dict[str, Any]:
    text_len = next((len(d[k]) for k in _DOC_TEXT_KEYS if isinstance(d.get(k), str)), 0)
    return {
        "index": i,
        "document_type": d.get("document_type"),
        "filename": d.get("filename") or d.get("name"),
        "uploaded_at": d.get("uploaded_at") or d.get("created_at"),
        "page_count": d.get("page_count") or d.get("pages"),
        "text_chars": text_len,
        "claim_number": d.get("claim_number"),
        "account_number": d.get("account_number"),
        "extraction_status": d.get("extraction_status") or d.get("status"),
    }


async def _journey(session: AsyncSession, cf: CaseFile) -> list[dict[str, Any]]:
    """The user's journey as the server knows it: the audit-lifecycle analytics events for
    this case (emitted from the status chokepoint), oldest first. Enum/number only by
    construction of the analytics registry."""
    from app.db.models.analytics_events import AnalyticsEvent

    rows = (
        (
            await session.execute(
                select(AnalyticsEvent)
                .where(AnalyticsEvent.case_file_id == cf.case_file_id)
                .order_by(AnalyticsEvent.occurred_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {"event": r.event_name, "at": _iso(r.occurred_at), "properties": r.properties or {}}
        for r in rows
    ]


@router.get("/admin/review/cases/{case_file_id}")
async def review_workspace(
    case_file_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The three-pane workspace. Opening a pending row moves it to in_review under this
    reviewer (a decided row is never downgraded); every open writes a review_view audit event."""
    from app.agents.orchestrator import _assemble_result, tripwire_entries
    from app.routes.conversations import message_to_out
    from app.sources.call_identifiers import of_case
    from app.sources.gameplan import build_gameplan

    cf = await _load_case(session, case_file_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    review = await review_queue.latest_review(session, cf.case_file_id)
    if review is not None and review.state in ("unreviewed", "re_review"):
        review.state = "in_review"
        review.reviewer_id = admin.user_id
        review.in_review_at = now
    await audit_admin_action(
        session,
        admin=admin,
        action="review_view",
        target_user_id=cf.user_id,
        case_file_id=cf.case_file_id,
        extra={
            "review_id": str(review.review_id) if review else None,
            "state": review.state if review else None,
        },
    )
    await session.commit()

    findings = (
        (
            await session.execute(
                select(Finding)
                .where(Finding.case_file_id == cf.case_file_id)
                .order_by(Finding.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    messages = (
        (
            await session.execute(
                select(Message)
                .join(Conversation, Message.conversation_id == Conversation.conversation_id)
                .where(Conversation.case_id == cf.case_file_id)
                .order_by(Message.created_at.asc(), Message.sequence_number.asc())
            )
        )
        .scalars()
        .all()
    )
    deadlines = (
        (await session.execute(select(Deadline).where(Deadline.case_file_id == cf.case_file_id)))
        .scalars()
        .all()
    )
    feedback = (
        (
            await session.execute(
                select(FeedbackEvent)
                .where(FeedbackEvent.case_file_id == cf.case_file_id)
                .order_by(FeedbackEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    verdicts = (
        (
            await session.execute(
                select(AdminVerdict)
                .where(AdminVerdict.case_file_id == cf.case_file_id)
                .order_by(AdminVerdict.captured_at.desc())
            )
        )
        .scalars()
        .all()
    )
    chain = (
        (
            await session.execute(
                select(CaseReview)
                .where(CaseReview.case_file_id == cf.case_file_id)
                .order_by(CaseReview.run_seq.asc())
            )
        )
        .scalars()
        .all()
    )

    audit: dict | None = None
    try:
        audit = (await _assemble_result(str(cf.case_file_id), composed="")).model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 — the rest of the workspace still renders
        log.warning("review.workspace.assemble_failed", case_file_id=case_file_id, error=str(exc))

    ids = of_case(cf)
    provenance = await case_provenance(case_file_id, admin=admin, session=session)
    provenance.update(
        {
            "tripwires": tripwire_entries(cf),
            "research_log": cf.research_log or [],
            "api_pulls": _PHASE2_PLACEHOLDER,
            "live_lookups": _PHASE2_PLACEHOLDER,
            "missing_data": _PHASE2_PLACEHOLDER,
            "retrieval_misses": _PHASE2_PLACEHOLDER,
        }
    )
    outcomes = [
        {
            "feedback_type": fb.feedback_type,
            "created_at": _iso(fb.created_at),
            "payload": fb.payload,
        }
        for fb in feedback
        if fb.feedback_type == "outcome_report"
        or (isinstance(fb.payload, dict) and fb.payload.get("call_outcome"))
    ]
    verdict_by_id = {v.verdict_id: v for v in verdicts}
    return {
        "case": {
            "case_file_id": str(cf.case_file_id),
            "user_masked": _mask(cf.user_id),
            "status": cf.status,
            "incomplete_reason": cf.audit_incomplete_reason,
            "intake_status": getattr(cf, "intake_status", None),
            "created_at": _iso(cf.created_at),
            "updated_at": _iso(cf.updated_at),
        },
        "review": _review_dict(
            review, now=now, verdict=verdict_by_id.get(review.verdict_id), user_id=cf.user_id
        )
        if review
        else None,
        "review_chain": [
            _review_dict(r, now=now, verdict=verdict_by_id.get(r.verdict_id), user_id=cf.user_id)
            for r in chain
        ],
        "left": {
            "documents": [
                _document_card(i, d)
                for i, d in enumerate(cf.documents or [])
                if isinstance(d, dict)
            ],
            "eobs": [
                _document_card(i, d) for i, d in enumerate(cf.eobs or []) if isinstance(d, dict)
            ],
            "extraction": {
                "line_items": cf.line_items or [],
                "coverage": cf.coverage or {},
                "encounter_confirmations": getattr(cf, "encounter_confirmations", None) or [],
            },
            "journey": await _journey(session, cf),
        },
        "tabs": {
            "analysis": {
                "three_numbers": (audit or {}).get("audit"),
                "disclosure": (audit or {}).get("disclosure"),
                "summary": (audit or {}).get("summary") or "",
                "result_status": (audit or {}).get("status"),
                "documents_needed": (audit or {}).get("documents_needed") or [],
                "findings": [_analysis_finding(f) for f in findings],
            },
            "conversation": [message_to_out(m).model_dump(mode="json") for m in messages],
            "results": {
                "gameplan": [g.model_dump(mode="json") for g in build_gameplan(findings, ids)],
                "identifiers": {
                    "claim_number": ids.claim_number,
                    "account_number": ids.account_number,
                    "provider_phone": ids.provider_phone,
                    "payer_phone": ids.payer_phone,
                },
                "tiers": [
                    {
                        "finding_id": str(f.finding_id),
                        "voice_tier": f.voice_tier,
                        "tier_a_facts": as_dict(f.facts) or {},
                        "tier_b_claim": f.legal_claim,
                        "tier_c_recommendation": f.recommendation,
                    }
                    for f in findings
                ],
                "deadlines": [
                    {
                        "deadline_id": str(d.deadline_id),
                        "deadline_date": d.deadline_date.isoformat() if d.deadline_date else None,
                        "deadline_type": d.deadline_type,
                        "status": d.status,
                    }
                    for d in deadlines
                ],
                "outcomes": outcomes,
            },
            "provenance": provenance,
        },
        "verdicts": [_verdict_dict(v) for v in verdicts],
    }


# ── verdicts ─────────────────────────────────────────────────────────────────────────────


class StructuredNote(BaseModel):
    concluded: str
    should_have_concluded: str
    input_or_rule: str


class ReviewVerdictRequest(BaseModel):
    action: Literal["approve", "disapprove", "cant_verify"]
    note: str | None = None
    verdict_type: str | None = None  # disapprove only — one of DISAPPROVAL_TYPES
    scope: Literal["whole_case", "findings"] | None = None  # disapprove only
    target_findings: list[str] | None = None  # scope == findings
    cause: str | None = None  # disapprove only — exactly one of CAUSES
    structured_note: StructuredNote | None = None  # disapprove only


@router.post("/admin/review/cases/{case_file_id}/verdict")
async def review_verdict(
    case_file_id: str,
    body: ReviewVerdictRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Approve (optional note) / Disapprove… (type + scope + one cause + structured note) /
    Can't verify (unable_to_verify — excluded from the approval rate). Append-only: a new
    admin_verdicts row every time, the review row moves to the decided state. The work lives in
    app.review.verdicts.record_verdict — the legacy cases route is a strict alias of it."""
    cf = await _load_case(session, case_file_id)
    try:
        return await record_verdict(
            session,
            admin=admin,
            cf=cf,
            via="review",
            v=VerdictInput(
                action=body.action,
                note=body.note,
                verdict_type=body.verdict_type,
                scope=body.scope,
                target_findings=body.target_findings,
                cause=body.cause,
                structured_note=body.structured_note.model_dump() if body.structured_note else None,
            ),
        )
    except VerdictRejected as exc:
        raise HTTPException(status_code=422, detail=exc.problems) from exc
