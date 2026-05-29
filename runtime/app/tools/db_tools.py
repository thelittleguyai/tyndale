"""Postgres-backed tools — case file get + finding/deadline upserts.

Matches the actual ORM models in ``app/db/models/`` (case_files PK is
``case_file_id``; findings PK is ``finding_id``; deadlines PK is
``deadline_id``, date field is ``deadline_date``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.deadlines import Deadline
from app.db.models.findings import Finding
from app.tools import register_tool

log = structlog.get_logger(__name__)


def _uuid(s: str | UUID) -> UUID:
    return s if isinstance(s, UUID) else UUID(str(s))


# --- pg_case_file_get -------------------------------------------------------
async def _pg_case_file_get(args: dict[str, Any]) -> dict[str, Any]:
    case_file_id = _uuid(args["case_file_id"])
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(CaseFile).where(CaseFile.case_file_id == case_file_id))
        cf = result.scalar_one_or_none()
        if cf is None:
            return {"error": f"case_file {case_file_id} not found"}
        return {
            "case_file_id": str(cf.case_file_id),
            "user_id": str(cf.user_id),
            "status": cf.status,
            "documents": cf.documents or [],
            "coverage": cf.coverage,
            "eobs": cf.eobs or [],
            "plan_current": cf.plan_current,
            "research_log": cf.research_log or [],
            "created_at": cf.created_at.isoformat() if cf.created_at else None,
        }


register_tool(
    "pg_case_file_get",
    {
        "description": (
            "Read the case file — status, uploaded documents, current coverage, EOB array, "
            "plan-to-memory, and the research_log (Change Order 001 item 4)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"case_file_id": {"type": "string", "description": "UUID"}},
            "required": ["case_file_id"],
        },
    },
    _pg_case_file_get,
)


# --- pg_upsert_finding ------------------------------------------------------
async def _pg_upsert_finding(args: dict[str, Any]) -> dict[str, Any]:
    case_file_id = _uuid(args["case_file_id"])
    finding_id = uuid4()

    # The Finding ORM model has no separate citations column. Store any
    # citation list inside legal_claim["citations"] so the orchestrator can
    # extract them when projecting to the FindingOut response.
    legal_claim = args.get("legal_claim")
    citations = args.get("citations")
    if citations and isinstance(legal_claim, dict):
        legal_claim = {**legal_claim, "citations": citations}
    elif citations:
        legal_claim = {"citations": citations}

    async with AsyncSessionLocal() as s:
        s.add(
            Finding(
                finding_id=finding_id,
                case_file_id=case_file_id,
                finding_type=args["finding_type"],
                category=args["category"],
                subagent_source=args.get("subagent_source", "unknown"),
                voice_tier=args.get("voice_tier", "B"),
                facts=args.get("facts", {}),
                legal_claim=legal_claim,
                recommendation=args.get("recommendation"),
            )
        )
        await s.commit()
    return {
        "finding_id": str(finding_id),
        "case_file_id": str(case_file_id),
        "stored": True,
    }


register_tool(
    "pg_upsert_finding",
    {
        "description": (
            "Persist a finding to the case file. finding_type ∈ {payer_side, provider_side, "
            "encounter_mismatch}. voice_tier ∈ {A, B, C}. facts is a Tier A structured dict. "
            "legal_claim is the Tier B claim object (include citations as a list inside it). "
            "recommendation is the Tier C scripted next-action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "case_file_id": {"type": "string"},
                "finding_type": {"type": "string", "enum": ["payer_side", "provider_side", "encounter_mismatch"]},
                "category": {"type": "string"},
                "facts": {"type": "object"},
                "legal_claim": {"type": "object"},
                "recommendation": {"type": "object"},
                "citations": {"type": "array", "items": {"type": "object"}},
                "voice_tier": {"type": "string", "enum": ["A", "B", "C"]},
                "subagent_source": {"type": "string"},
            },
            "required": ["case_file_id", "finding_type", "category"],
        },
    },
    _pg_upsert_finding,
)


# --- pg_deadline_upsert -----------------------------------------------------
async def _pg_deadline_upsert(args: dict[str, Any]) -> dict[str, Any]:
    case_file_id = _uuid(args["case_file_id"])
    deadline_date_iso = args["deadline_date"]
    deadline_type = args["deadline_type"]
    description = args["description"]

    d = date.fromisoformat(deadline_date_iso[:10])
    deadline_id = uuid4()
    async with AsyncSessionLocal() as s:
        s.add(
            Deadline(
                deadline_id=deadline_id,
                case_file_id=case_file_id,
                deadline_date=d,
                deadline_type=deadline_type,
                description=description,
            )
        )
        await s.commit()
    return {"deadline_id": str(deadline_id), "deadline_date": d.isoformat()}


register_tool(
    "pg_deadline_upsert",
    {
        "description": "Persist a deadline (appeal window, payment due, EOB-receipt window, …) for a case.",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_file_id": {"type": "string"},
                "deadline_type": {"type": "string"},
                "deadline_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "description": {"type": "string"},
            },
            "required": ["case_file_id", "deadline_type", "deadline_date", "description"],
        },
    },
    _pg_deadline_upsert,
)


# --- pg_list_due ------------------------------------------------------------
async def _pg_list_due(args: dict[str, Any]) -> dict[str, Any]:
    case_file_id = args.get("case_file_id")
    within_days = int(args.get("within_days", 30))
    from datetime import timedelta

    cutoff = datetime.utcnow().date() + timedelta(days=within_days)
    async with AsyncSessionLocal() as s:
        q = select(Deadline).order_by(Deadline.deadline_date.asc())
        if case_file_id:
            q = q.where(Deadline.case_file_id == _uuid(case_file_id))
        rows = (await s.execute(q)).scalars().all()
        out = [
            {
                "deadline_id": str(d.deadline_id),
                "case_file_id": str(d.case_file_id),
                "deadline_type": d.deadline_type,
                "deadline_date": d.deadline_date.isoformat(),
                "description": d.description,
                "status": d.status,
            }
            for d in rows
            if d.deadline_date <= cutoff
        ]
    return {"deadlines": out, "count": len(out)}


register_tool(
    "pg_list_due",
    {
        "description": "List deadlines due within N days for a case or across all cases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_file_id": {"type": "string"},
                "within_days": {"type": "integer", "default": 30},
            },
        },
    },
    _pg_list_due,
)
