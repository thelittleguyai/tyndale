"""Admin console routes (Phase CO-6A) — Brock-only case review + verdict capture.

DL-60 dual-layer auth: this is the APP layer — every route requires
`current_user.user_type == 'admin'`, and a non-admin gets **404** (anti-
enumeration; never reveal the console exists). The NETWORK layer (Container Apps
ingress IP allowlist) is in infra/. These routes inherit the same rate limit +
security headers + JWT validation as every other /v1/* route (Phase 2K.2).

MVP scope: case browse, case detail, data-point provenance tree, verdict capture.
NO chat-driven correction (that's CO-6B, Sprint D).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.findings import Finding
from app.db.models.users import User
from app.db.session import get_session

router = APIRouter(tags=["v1-admin"])


# --------------------------------------------------------------------------- #
# Admin gate (DL-60: non-admin → 404, not 403)
# --------------------------------------------------------------------------- #
async def admin_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if user.user_type != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    return user


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as e:
        raise HTTPException(status_code=404, detail="Not Found") from e


def _iso(dt: datetime.datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _decode_payload(ev: AuditEvent) -> dict:
    """Phase-1C audit payloads are clear-text JSON bytes (AES-GCM in Phase 4)."""
    try:
        return json.loads(bytes(ev.payload_encrypted).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, TypeError):
        return {}


async def _load_case(session: AsyncSession, case_file_id: str) -> CaseFile:
    cf = (
        await session.execute(select(CaseFile).where(CaseFile.case_file_id == _uuid(case_file_id)))
    ).scalar_one_or_none()
    if cf is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return cf


# --------------------------------------------------------------------------- #
# Case browse
# --------------------------------------------------------------------------- #
@router.get("/admin/cases")
async def list_cases(
    status: str | None = None,
    user_id: str | None = None,
    has_verdict: bool | None = None,
    since: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    q = select(CaseFile)
    if status:
        q = q.where(CaseFile.status == status)
    if user_id:
        q = q.where(CaseFile.user_id == _uuid(user_id))
    if since:
        try:
            q = q.where(CaseFile.created_at >= datetime.datetime.fromisoformat(since))
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid 'since' (use ISO-8601)") from None
    q = q.order_by(CaseFile.created_at.desc()).limit(min(max(limit, 1), 200)).offset(max(offset, 0))
    cases = (await session.execute(q)).scalars().all()

    uids = {c.user_id for c in cases}
    emails: dict[uuid.UUID, str] = {}
    if uids:
        emails = {
            u.user_id: u.email
            for u in (await session.execute(select(User).where(User.user_id.in_(uids))))
            .scalars()
            .all()
        }
    cfids = [c.case_file_id for c in cases]
    verdicted: set[uuid.UUID] = set()
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


# --------------------------------------------------------------------------- #
# Case detail
# --------------------------------------------------------------------------- #
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
        # No conversation/messages model in V1-Lite yet — chat history lands later.
        "conversation_history": [],
        # Full three-number audit is available via GET /v1/audit/{id}; not duplicated here.
        "last_audit_result": None,
    }


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


# --------------------------------------------------------------------------- #
# Provenance tree (CO-002 Item 6.A)
# --------------------------------------------------------------------------- #
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
        # The 7 provenance groups (CO-002 Item 6.A) — always present, possibly empty.
        "documents": cf.documents or [],
        "skills_loaded": sorted(skills),
        "tools_called": tools_called,
        "qdrant_chunks_retrieved": qdrant_chunks,
        "subagent_calls": subagent_calls,
        "findings_written": [_finding_dict(f) for f in findings],
        "llm_calls": llm_calls,
    }


# --------------------------------------------------------------------------- #
# Verdict capture
# --------------------------------------------------------------------------- #
class VerdictRequest(BaseModel):
    verdict: Literal["correct", "partially_correct", "wrong"]
    notes: str | None = None
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
        target_findings=req.target_findings,
        target_response=req.target_response,
    )
    session.add(verdict)
    await session.flush()
    verdict_id = verdict.verdict_id

    # Audit (same clear-text-payload discipline as the rest of the runtime).
    payload = {
        "action": "admin_verdict",
        "verdict": req.verdict,
        "target_findings": req.target_findings,
        "target_response": req.target_response,
        "verdict_id": str(verdict_id),
    }
    body = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    session.add(
        AuditEvent(
            event_type="user_action",
            actor=admin.email,
            case_file_id=cf.case_file_id,
            user_id=admin.user_id,
            payload_encrypted=body,
            payload_hash=hashlib.sha256(body).digest(),
            key_version=0,
            tools_invoked=None,
            outcome="success",
        )
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


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
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
        "shadow_appeals_pending": 0,  # populated when CO-5A shadow appeals land
    }
