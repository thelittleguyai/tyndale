"""Qdrant-backed knowledge retrieval tools.

Wraps the Phase 1D ``app.knowledge.search`` module. ``laws_regulations`` and
``payer_policies`` collections REQUIRE ``effective_date`` — that's enforced
both here (clear ValueError) and inside ``search.search()`` (defense-in-depth
with the PreToolUse hook).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.knowledge.search import search_and_rerank
from app.tools import register_tool

log = structlog.get_logger(__name__)


def _hits_to_payload(hits) -> list[dict[str, Any]]:
    return [{"id": str(h.id), "score": h.score, "payload": h.payload} for h in hits]


# --- qdrant_search_billing_codes --------------------------------------------
async def _qdrant_search_billing_codes(args: dict[str, Any]) -> dict[str, Any]:
    hits = await search_and_rerank(
        collection="billing_codes",
        query=args["query"],
        filters=args.get("filters"),
        top_k=int(args.get("top_k", 30)),
        top_n=int(args.get("top_n", 8)),
    )
    return {"hits": _hits_to_payload(hits), "count": len(hits)}


register_tool(
    "qdrant_search_billing_codes",
    {
        "description": "Search CPT/HCPCS/ICD-10 catalog for codes, descriptors, modifier rules.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
                "top_k": {"type": "integer", "default": 30},
                "top_n": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },
    _qdrant_search_billing_codes,
)


# --- qdrant_search_error_detection_rules ------------------------------------
async def _qdrant_search_error_detection_rules(args: dict[str, Any]) -> dict[str, Any]:
    hits = await search_and_rerank(
        collection="error_detection_rules",
        query=args["query"],
        filters=args.get("filters"),
        top_k=int(args.get("top_k", 30)),
        top_n=int(args.get("top_n", 8)),
    )
    return {"hits": _hits_to_payload(hits), "count": len(hits)}


register_tool(
    "qdrant_search_error_detection_rules",
    {
        "description": "Search Tyndale's curated error-detection rule library (the 23 checks + variants).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
                "top_k": {"type": "integer", "default": 30},
                "top_n": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },
    _qdrant_search_error_detection_rules,
)


# --- qdrant_search_laws_regulations -----------------------------------------
async def _qdrant_search_laws_regulations(args: dict[str, Any]) -> dict[str, Any]:
    if not args.get("effective_date"):
        return {"error": "effective_date is REQUIRED for laws_regulations queries"}
    hits = await search_and_rerank(
        collection="laws_regulations",
        query=args["query"],
        effective_date=args["effective_date"],
        filters=args.get("filters"),
        top_k=int(args.get("top_k", 30)),
        top_n=int(args.get("top_n", 8)),
    )
    return {"hits": _hits_to_payload(hits), "count": len(hits)}


register_tool(
    "qdrant_search_laws_regulations",
    {
        "description": (
            "Point-in-time search of statutes / federal regs (ACA, NSA, ERISA, MHPAEA, "
            "IRS §501(r)). effective_date is REQUIRED — supply the date the event happened "
            "(usually the date-of-service) so the right historical version is returned."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "effective_date": {"type": "string", "description": "ISO date (YYYY-MM-DD)"},
                "filters": {"type": "object"},
                "top_k": {"type": "integer", "default": 30},
                "top_n": {"type": "integer", "default": 8},
            },
            "required": ["query", "effective_date"],
        },
    },
    _qdrant_search_laws_regulations,
)


# --- qdrant_search_payer_policies -------------------------------------------
async def _qdrant_search_payer_policies(args: dict[str, Any]) -> dict[str, Any]:
    if not args.get("effective_date"):
        return {"error": "effective_date is REQUIRED for payer_policies queries"}
    hits = await search_and_rerank(
        collection="payer_policies",
        query=args["query"],
        effective_date=args["effective_date"],
        filters=args.get("filters"),
        top_k=int(args.get("top_k", 30)),
        top_n=int(args.get("top_n", 8)),
    )
    return {"hits": _hits_to_payload(hits), "count": len(hits)}


register_tool(
    "qdrant_search_payer_policies",
    {
        "description": (
            "Point-in-time search of payer medical/payment policies. effective_date is REQUIRED "
            "for the same point-in-time reasons as laws_regulations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "effective_date": {"type": "string"},
                "filters": {"type": "object"},
                "top_k": {"type": "integer", "default": 30},
                "top_n": {"type": "integer", "default": 8},
            },
            "required": ["query", "effective_date"],
        },
    },
    _qdrant_search_payer_policies,
)
