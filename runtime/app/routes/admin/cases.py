"""Admin case browse + detail + provenance + verdict capture (CO-6A, moved into the
admin package by CO-9). Module 3 extends these (5-option verdict, richer filters, export).

DL-60 dual-layer auth: every route requires admin (non-admin → 404).
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.conversations import Conversation
from app.db.models.deadlines import Deadline
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.db.models.messages import Message
from app.db.models.users import User
from app.db.session import get_session
from app.routes.admin._deps import admin_user
from app.routes.admin._deps import admin_uuid as _uuid
from app.routes.admin._deps import audit_admin_action
from app.routes.admin._deps import decode_payload as _decode_payload
from app.routes.admin._deps import iso as _iso

router = APIRouter(tags=["v1-admin"])


async def _load_case(session: AsyncSession, case_file_id: str) -> CaseFile:
    cf = (
        await session.execute(select(CaseFile).where(CaseFile.case_file_id == _uuid(case_file_id)))
    ).scalar_one_or_none()
    if cf is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return cf


def _finding_dict(f: Finding) -> dict:
    return {
        "finding_id": str(f.finding_id),
        "finding_type": f.finding_type,
        "category": f.category,
        "subagent_source": f.subagent_source,
        "voice_tier": f.voice_tier,
        "facts": f.facts or {},
        "legal_claim": f.legal_claim,
        "recommendation": f.recommendation,
        "status": f.status,
    }


@router.get("/admin/cases")
async def list_cases(
    status: str | None = None,
    user_id: str | None = None,
    has_verdict: bool | None = None,
    verdict: str | None = None,
    search: str | None = Query(None, alias="q"),
    since: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    # NOTE: encounter_type / payer / total_charge_bucket filters are JSONB-derived and
    # deferred (they live in line_items/coverage, not columns) — accepted by the UI but
    # not yet pushed into SQL.
    stmt = select(CaseFile)
    if status:
        stmt = stmt.where(CaseFile.status == status)
    if user_id:
        stmt = stmt.where(CaseFile.user_id == _uuid(user_id))
    if search:  # matches case-id OR a CPT/text token inside the line items
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                CaseFile.case_file_id.cast(String).ilike(like),
                CaseFile.line_items.cast(String).ilike(like),
            )
        )
    for raw, lower_bound in ((since, True), (date_from, True), (date_to, False)):
        if not raw:
            continue
        try:
            dt = datetime.datetime.fromisoformat(raw)
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid date (use ISO-8601)") from None
        stmt = stmt.where(CaseFile.created_at >= dt if lower_bound else CaseFile.created_at <= dt)
    if verdict:
        stmt = stmt.where(
            CaseFile.case_file_id.in_(
                select(AdminVerdict.case_file_id).where(AdminVerdict.verdict == verdict)
            )
        )
    stmt = (
        stmt.order_by(CaseFile.created_at.desc())
        .limit(min(max(limit, 1), 200))
        .offset(max(offset, 0))
    )
    cases = (await session.execute(stmt)).scalars().all()

    uids = {c.user_id for c in cases}
    emails: dict[Any, str] = {}
    if uids:
        emails = {
            u.user_id: u.email
            for u in (await session.execute(select(User).where(User.user_id.in_(uids))))
            .scalars()
            .all()
        }
    cfids = [c.case_file_id for c in cases]
    verdicted: set[Any] = set()
    if cfids:
        verdicted = set(
            (
                await session.execute(
                    select(AdminVerdict.case_file_id).where(AdminVerdict.case_file_id.in_(cfids))
                )
            )
            .scalars()
            .all()
        )

    out: list[dict] = []
    for c in cases:
        vs = "captured" if c.case_file_id in verdicted else "pending"
        if has_verdict is not None and has_verdict != (vs == "captured"):
            continue
        out.append(
            {
                "case_file_id": str(c.case_file_id),
                "user_email": emails.get(c.user_id),
                "status": c.status,
                "intake_status": getattr(c, "intake_status", None),
                "created_at": _iso(c.created_at),
                "last_activity_at": _iso(c.updated_at),
                "verdict_status": vs,
                "summary": f"{c.status} · {len(c.documents or [])} doc(s)",
            }
        )
    return {"cases": out, "count": len(out)}


@router.get("/admin/cases/{case_file_id}")
async def case_detail(
    case_file_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    cf = await _load_case(session, case_file_id)
    user = (
        await session.execute(select(User).where(User.user_id == cf.user_id))
    ).scalar_one_or_none()
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
    deadlines = (
        (
            await session.execute(
                select(Deadline)
                .where(Deadline.case_file_id == cf.case_file_id)
                .order_by(Deadline.deadline_date.asc())
            )
        )
        .scalars()
        .all()
    )

    feedback = (
        (
            await session.execute(
                select(FeedbackEvent)
                .where(FeedbackEvent.case_file_id == cf.case_file_id)
                .order_by(FeedbackEvent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest_verdict = (
        await session.execute(
            select(AdminVerdict)
            .where(AdminVerdict.case_file_id == cf.case_file_id)
            .order_by(AdminVerdict.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Real chat transcript (CO-10 conversation store): every message across the
    # per-case conversations for this case, ordered chronologically. Projected to
    # the {role, content, timestamp} shape the admin ChatTranscript renders.
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
    conversation_history = [
        {
            "role": m.role,
            "content": m.content or "",
            "timestamp": _iso(m.created_at),
        }
        for m in messages
    ]

    # Real last audit result: project the persisted findings to the AuditResult
    # shape (three-number audit + findings + status) the runtime already assembles
    # for /v1/audit. Kept best-effort so a case with un-projectable findings still
    # renders the rest of the detail page.
    last_audit_result: dict | None = None
    try:
        from app.agents.orchestrator import _assemble_result

        audit = await _assemble_result(str(cf.case_file_id), composed="")
        last_audit_result = audit.model_dump(mode="json")
    except Exception:  # noqa: BLE001 — degrade gracefully; the Findings tab still shows raw findings
        last_audit_result = None

    return {
        "case_file_id": str(cf.case_file_id),
        "user": {
            "user_id": str(cf.user_id),
            "email": user.email if user else None,
            "user_type": user.user_type if user else None,
        },
        "status": cf.status,
        "created_at": _iso(cf.created_at),
        "updated_at": _iso(cf.updated_at),
        "intake_status": getattr(cf, "intake_status", None),
        "visit_context": getattr(cf, "visit_context", None),
        "coverage": cf.coverage or {},
        "documents": cf.documents or [],
        "eobs": cf.eobs or [],
        "findings": [_finding_dict(f) for f in findings],
        "deadlines": [
            {
                "deadline_id": str(d.deadline_id),
                "deadline_date": d.deadline_date.isoformat() if d.deadline_date else None,
                "deadline_type": d.deadline_type,
                "description": d.description,
                "status": d.status,
            }
            for d in deadlines
        ],
        "research_log": cf.research_log or [],
        "plan_versions": {"current": cf.plan_current, "history": cf.plan_history or []},
        "conversation_history": conversation_history,
        "last_audit_result": last_audit_result,
        "user_feedback": [
            {
                "feedback_type": fb.feedback_type,
                "created_at": _iso(fb.created_at),
                "payload": fb.payload,
            }
            for fb in feedback
        ],
        "latest_verdict": (
            {
                "verdict_id": str(latest_verdict.verdict_id),
                "verdict": latest_verdict.verdict,
                "notes": latest_verdict.notes,
                "missed_findings": latest_verdict.missed_findings,
                "hallucinated_claims": latest_verdict.hallucinated_claims,
                "captured_at": _iso(latest_verdict.captured_at),
            }
            if latest_verdict
            else None
        ),
    }


@router.get("/admin/cases/{case_file_id}/provenance")
async def case_provenance(
    case_file_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    cf = await _load_case(session, case_file_id)
    events = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.case_file_id == cf.case_file_id)
                .order_by(AuditEvent.timestamp.asc())
            )
        )
        .scalars()
        .all()
    )
    findings = (
        (await session.execute(select(Finding).where(Finding.case_file_id == cf.case_file_id)))
        .scalars()
        .all()
    )

    tools_called: list[dict] = []
    subagent_calls: list[dict] = []
    llm_calls: list[dict] = []
    qdrant_chunks: list[Any] = []
    skills: set[str] = set()

    for ev in events:
        payload = _decode_payload(ev)
        if ev.skill_version:
            skills.add(ev.skill_version)
        if ev.retrieved_chunks:
            qdrant_chunks.extend(ev.retrieved_chunks)
        if ev.event_type == "tool_invocation":
            tools_called.append(
                {
                    "tools_invoked": ev.tools_invoked,
                    "args": payload.get("tool_args_scrubbed"),
                    "result": payload.get("tool_result"),
                    "outcome": ev.outcome,
                    "timestamp": _iso(ev.timestamp),
                }
            )
        elif ev.event_type == "subagent_call":
            subagent_calls.append(
                {
                    "actor": ev.actor,
                    "outcome": ev.outcome,
                    "timestamp": _iso(ev.timestamp),
                    "detail": payload,
                }
            )
        elif ev.event_type == "model_call":
            llm_calls.append(
                {
                    "model": ev.model_version,
                    "outcome": ev.outcome,
                    "timestamp": _iso(ev.timestamp),
                    "usage": payload.get("usage"),
                }
            )

    return {
        "case_file_id": str(cf.case_file_id),
        "documents": cf.documents or [],
        "skills_loaded": sorted(skills),
        "tools_called": tools_called,
        "qdrant_chunks_retrieved": qdrant_chunks,
        "subagent_calls": subagent_calls,
        "findings_written": [_finding_dict(f) for f in findings],
        "llm_calls": llm_calls,
    }


class VerdictRequest(BaseModel):
    # CO-9 Module 3 verdict v2 — the 5-option fine-tune vocabulary.
    verdict: Literal["correct", "missed_finding", "hallucinated", "partial", "unable_to_verify"]
    notes: str | None = None
    missed_findings: list[str] | None = None
    hallucinated_claims: list[str] | None = None
    target_findings: list[str] | None = None  # null = whole case
    target_response: str | None = None  # null = latest


@router.post("/admin/cases/{case_file_id}/verdict")
async def submit_verdict(
    case_file_id: str,
    req: VerdictRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    cf = await _load_case(session, case_file_id)
    verdict = AdminVerdict(
        case_file_id=cf.case_file_id,
        admin_user_id=admin.user_id,
        verdict=req.verdict,
        notes=req.notes,
        missed_findings=req.missed_findings,
        hallucinated_claims=req.hallucinated_claims,
        target_findings=req.target_findings,
        target_response=req.target_response,
    )
    session.add(verdict)
    await session.flush()
    verdict_id = verdict.verdict_id

    await audit_admin_action(
        session,
        admin=admin,
        action="verdict",
        target_user_id=cf.user_id,
        case_file_id=cf.case_file_id,
        extra={
            "verdict": req.verdict,
            "missed_findings": req.missed_findings,
            "hallucinated_claims": req.hallucinated_claims,
            "verdict_id": str(verdict_id),
        },
    )
    await session.commit()
    return {"verdict_id": str(verdict_id), "stored": True}


@router.get("/admin/cases/{case_file_id}/verdicts")
async def list_verdicts(
    case_file_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    cf = await _load_case(session, case_file_id)
    rows = (
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
    return {
        "case_file_id": str(cf.case_file_id),
        "verdicts": [
            {
                "verdict_id": str(v.verdict_id),
                "verdict": v.verdict,
                "notes": v.notes,
                "target_findings": v.target_findings,
                "target_response": v.target_response,
                "admin_user_id": str(v.admin_user_id),
                "captured_at": _iso(v.captured_at),
            }
            for v in rows
        ],
    }


@router.get("/admin/cases/{case_file_id}/export")
async def export_case(
    case_file_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Full case export for offline regression analysis: uploads, encounters, reasoning
    trail, findings, feedback, verdicts."""
    cf = await _load_case(session, case_file_id)
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
    events = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.case_file_id == cf.case_file_id)
                .order_by(AuditEvent.timestamp.asc())
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
    feedback = (
        (
            await session.execute(
                select(FeedbackEvent)
                .where(FeedbackEvent.case_file_id == cf.case_file_id)
                .order_by(FeedbackEvent.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    await audit_admin_action(
        session,
        admin=admin,
        action="case_export",
        target_user_id=cf.user_id,
        case_file_id=cf.case_file_id,
    )
    await session.commit()
    return {
        "case_file_id": str(cf.case_file_id),
        "exported_at": _iso(datetime.datetime.now(datetime.timezone.utc)),
        "user_id": str(cf.user_id),
        "status": cf.status,
        "documents": cf.documents or [],
        "coverage": cf.coverage or {},
        "eobs": cf.eobs or [],
        "line_items": cf.line_items or [],
        "encounter_confirmations": cf.encounter_confirmations or [],
        "research_log": cf.research_log or [],
        "findings": [_finding_dict(f) for f in findings],
        "reasoning_trail": [
            {
                "event_type": ev.event_type,
                "actor": ev.actor,
                "timestamp": _iso(ev.timestamp),
                "outcome": ev.outcome,
                "tools_invoked": ev.tools_invoked,
                "payload": _decode_payload(ev),
            }
            for ev in events
        ],
        "feedback": [
            {
                "feedback_type": fb.feedback_type,
                "created_at": _iso(fb.created_at),
                "payload": fb.payload,
            }
            for fb in feedback
        ],
        "verdicts": [
            {
                "verdict_id": str(v.verdict_id),
                "verdict": v.verdict,
                "notes": v.notes,
                "missed_findings": v.missed_findings,
                "hallucinated_claims": v.hallucinated_claims,
                "target_findings": v.target_findings,
                "captured_at": _iso(v.captured_at),
            }
            for v in verdicts
        ],
    }


@router.get("/admin/dashboard")
async def admin_dashboard(
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    open_cases_count = (
        await session.execute(
            select(func.count())
            .select_from(CaseFile)
            .where(CaseFile.status.in_(("open", "in_progress")))
        )
    ).scalar_one()
    total_cases = (await session.execute(select(func.count()).select_from(CaseFile))).scalar_one()
    verdicted_cases = (
        await session.execute(select(func.count(func.distinct(AdminVerdict.case_file_id))))
    ).scalar_one()
    recent = (
        (
            await session.execute(
                select(AdminVerdict).order_by(AdminVerdict.captured_at.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )

    return {
        "open_cases_count": int(open_cases_count or 0),
        "pending_verdict_count": int((total_cases or 0) - (verdicted_cases or 0)),
        "recent_verdicts": [
            {
                "verdict_id": str(v.verdict_id),
                "case_file_id": str(v.case_file_id),
                "verdict": v.verdict,
                "captured_at": _iso(v.captured_at),
            }
            for v in recent
        ],
        "shadow_appeals_pending": 0,
    }
