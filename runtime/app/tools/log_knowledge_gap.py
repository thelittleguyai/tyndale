"""log_knowledge_gap tool (Phase CO-9, Module 6).

A subagent calls this when it hits a data gap:
  - no_data        : queried the data/knowledge layer and got zero results
  - low_confidence : got results but the top score was below threshold
  - self_reported  : reasoned "I don't have data on X"

Rows feed the admin gap dashboard that drives "what should the team ingest next" — from
real subagent reporting, not guesses.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

import structlog

from app.db.base import AsyncSessionLocal
from app.db.models.knowledge_gap_log import KnowledgeGapLog
from app.tools import register_tool

log = structlog.get_logger(__name__)


def _coerce(v: Any) -> uuid.UUID | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


async def log_knowledge_gap(
    *,
    agent_name: str,
    gap_type: Literal["no_data", "low_confidence", "self_reported"],
    query: str,
    case_id: uuid.UUID | str | None = None,
    user_id: uuid.UUID | str | None = None,
    context_summary: str | None = None,
    confidence_score: float | None = None,
) -> uuid.UUID:
    """Insert a knowledge_gap_log row; returns the gap_id."""
    async with AsyncSessionLocal() as s:
        gap = KnowledgeGapLog(
            case_id=_coerce(case_id),
            user_id=_coerce(user_id),
            agent_name=agent_name,
            gap_type=gap_type,
            query=query,
            context_summary=context_summary,
            confidence_score=confidence_score,
        )
        s.add(gap)
        await s.commit()
        log.info(
            "knowledge_gap.logged", agent=agent_name, gap_type=gap_type, gap_id=str(gap.gap_id)
        )
        return gap.gap_id


async def _tool(args: dict[str, Any]) -> dict[str, Any]:
    gap_id = await log_knowledge_gap(
        agent_name=args.get("agent_name", "unknown"),
        gap_type=args.get("gap_type", "self_reported"),
        query=args.get("query", ""),
        case_id=args.get("case_id"),
        user_id=args.get("user_id"),
        context_summary=args.get("context_summary"),
        confidence_score=args.get("confidence_score"),
    )
    return {"gap_id": str(gap_id), "logged": True}


register_tool(
    "log_knowledge_gap",
    {
        "description": (
            "Record a knowledge gap when you queried the data layer and found nothing "
            "(no_data), found weak/low-score results (low_confidence), or reasoned that you "
            "lack data on something (self_reported). Feeds the team's ingestion-priority "
            "dashboard. Call once per distinct gap; keep 'query' the specific thing you needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["lead_planner", "bill_detective", "math_person"],
                },
                "gap_type": {
                    "type": "string",
                    "enum": ["no_data", "low_confidence", "self_reported"],
                },
                "query": {"type": "string"},
                "context_summary": {"type": "string"},
                "confidence_score": {"type": "number"},
                "case_id": {"type": "string"},
                "user_id": {"type": "string"},
            },
            "required": ["agent_name", "gap_type", "query"],
        },
    },
    _tool,
)
