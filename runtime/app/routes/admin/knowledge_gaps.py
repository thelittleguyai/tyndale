"""Admin knowledge-gap dashboard (Phase CO-9, Module 6).

List + aggregate subagent-reported gaps, and mark a gap (or cluster) resolved once
ingestion closes it. The feedback loop: "what to ingest next" comes from real gap-reporting.
"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.knowledge_gap_log import KnowledgeGapLog
from app.db.session import get_session
from app.routes.admin._deps import admin_user, admin_uuid, audit_admin_action, iso

router = APIRouter(tags=["v1-admin"])


def _gap_dict(g: KnowledgeGapLog) -> dict:
    return {
        "gap_id": str(g.gap_id),
        "case_id": str(g.case_id) if g.case_id else None,
        "agent_name": g.agent_name,
        "gap_type": g.gap_type,
        "query": g.query,
        "context_summary": g.context_summary,
        "confidence_score": float(g.confidence_score) if g.confidence_score is not None else None,
        "logged_at": iso(g.logged_at),
        "resolved_at": iso(g.resolved_at),
        "resolved_by_source": g.resolved_by_source,
    }


def _apply_resolved(stmt, resolved: str):
    if resolved == "true":
        return stmt.where(KnowledgeGapLog.resolved_at.isnot(None))
    if resolved == "false":
        return stmt.where(KnowledgeGapLog.resolved_at.is_(None))
    return stmt


@router.get("/admin/knowledge-gaps")
async def list_gaps(
    agent_name: str | None = None,
    gap_type: str | None = None,
    resolved: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    stmt = select(KnowledgeGapLog)
    if agent_name:
        stmt = stmt.where(KnowledgeGapLog.agent_name == agent_name)
    if gap_type:
        stmt = stmt.where(KnowledgeGapLog.gap_type == gap_type)
    stmt = _apply_resolved(stmt, resolved)
    for raw, lower in ((date_from, True), (date_to, False)):
        if raw:
            try:
                dt = datetime.datetime.fromisoformat(raw)
            except ValueError:
                raise HTTPException(status_code=422, detail="invalid date (ISO-8601)") from None
            stmt = stmt.where(
                KnowledgeGapLog.logged_at >= dt if lower else KnowledgeGapLog.logged_at <= dt
            )
    stmt = (
        stmt.order_by(KnowledgeGapLog.logged_at.desc())
        .limit(min(max(limit, 1), 200))
        .offset(max(offset, 0))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {"gaps": [_gap_dict(g) for g in rows], "count": len(rows)}


@router.get("/admin/knowledge-gaps/aggregate")
async def aggregate_gaps(
    group_by: str = "agent",
    resolved: str = "all",
    agent_name: str | None = None,
    gap_type: str | None = None,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if group_by in ("agent", "gap_type"):
        col = KnowledgeGapLog.agent_name if group_by == "agent" else KnowledgeGapLog.gap_type
        stmt = _apply_resolved(select(col, func.count()).group_by(col), resolved)
        rows = (await session.execute(stmt)).all()
        return {"group_by": group_by, "groups": [{"key": k, "count": n} for k, n in rows]}

    # cluster: cheap substring-clustering on the first 5 words of the query (V1).
    stmt = _apply_resolved(select(KnowledgeGapLog), resolved)
    if agent_name:
        stmt = stmt.where(KnowledgeGapLog.agent_name == agent_name)
    if gap_type:
        stmt = stmt.where(KnowledgeGapLog.gap_type == gap_type)
    rows = (await session.execute(stmt)).scalars().all()
    counter: Counter = Counter()
    representative: dict[str, str] = {}
    for g in rows:
        key = " ".join((g.query or "").lower().split()[:5])
        counter[key] += 1
        representative.setdefault(key, g.query)
    return {
        "group_by": "cluster",
        "clusters": [
            {"cluster": k, "representative_query": representative[k], "count": n}
            for k, n in counter.most_common(20)
        ],
    }


class ResolveRequest(BaseModel):
    resolved_by_source: str


@router.post("/admin/knowledge-gaps/{gap_id}/resolve")
async def resolve_gap(
    gap_id: str,
    req: ResolveRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    g = (
        await session.execute(
            select(KnowledgeGapLog).where(KnowledgeGapLog.gap_id == admin_uuid(gap_id))
        )
    ).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Not Found")
    g.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    g.resolved_by_source = req.resolved_by_source
    await audit_admin_action(
        session,
        admin=admin,
        action="resolve_knowledge_gap",
        extra={"gap_id": gap_id, "resolved_by_source": req.resolved_by_source},
    )
    await session.commit()
    return {"ok": True, "gap_id": gap_id}
