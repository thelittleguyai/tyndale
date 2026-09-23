"""Qdrant-backed knowledge retrieval tools.

Wraps the Phase 1D ``app.knowledge.search`` module. ``laws_regulations`` and
``payer_policies`` collections REQUIRE ``effective_date`` — that's enforced
both here (clear ValueError) and inside ``search.search()`` (defense-in-depth
with the PreToolUse hook).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.knowledge import health
from app.knowledge.embeddings import EmbeddingUnavailable
from app.knowledge.search import search_and_rerank, search_many
from app.tools import register_tool

log = structlog.get_logger(__name__)

KNOWLEDGE_TOOLS = (
    "qdrant_search_billing_codes",
    "qdrant_search_error_detection_rules",
    "qdrant_search_laws_regulations",
    "qdrant_search_payer_policies",
)
RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"


def _queries(args: dict[str, Any]) -> list[str]:
    """``queries`` (several at once — ONE embedding call) or the single ``query``."""
    qs = args.get("queries")
    if isinstance(qs, list) and qs:
        return [str(q) for q in qs if str(q).strip()]
    return [str(args["query"])]


async def _run_search(tool: str, collection: str, args: dict[str, Any], **kw: Any) -> dict[str, Any]:
    """Every knowledge tool goes through here (e2e 2026-09-23 B1): the outcome lands in the
    retrieval-health ledger, an embedding failure is reported as ONE typed reason the audit
    can recognise (``retrieval_unavailable``) instead of an HTTP traceback, and several
    queries share one embedding call."""
    queries = _queries(args)
    top_k, top_n = int(args.get("top_k", 30)), int(args.get("top_n", 8))
    try:
        if len(queries) == 1:
            per_query = [await search_and_rerank(collection=collection, query=queries[0], top_k=top_k, top_n=top_n, **kw)]
        else:
            per_query = await search_many(collection, queries, top_k=top_k, top_n=top_n, **kw)
    except EmbeddingUnavailable as exc:
        health.record_tool_call(tool, False, error=str(exc))
        return {"error": RETRIEVAL_UNAVAILABLE, "reason": str(exc)[:200], "hits": [], "count": 0}
    except Exception as exc:  # noqa: BLE001 — recorded, then re-raised for call_tool's contract
        health.record_tool_call(tool, False, error=str(exc))
        raise
    health.record_tool_call(tool, True)
    if len(queries) == 1:
        hits = per_query[0]
        return {"hits": _hits_to_payload(hits), "count": len(hits)}
    return {
        "results": [{"query": q, "hits": _hits_to_payload(h), "count": len(h)} for q, h in zip(queries, per_query, strict=True)],
        "count": sum(len(h) for h in per_query),
    }


def _hits_to_payload(hits) -> list[dict[str, Any]]:
    # The FULL stored record rides in ``payload`` untouched, so laws_regulations hits
    # carry ``as_of`` and ``x6_classification`` (DL-84) through to the model and to
    # ``_collect_retrieved_chunks`` → the chat Citation — no per-field projection here.
    return [{"id": str(h.id), "score": h.score, "payload": h.payload} for h in hits]


# --- qdrant_search_billing_codes --------------------------------------------
async def _qdrant_search_billing_codes(args: dict[str, Any]) -> dict[str, Any]:
    return await _run_search("qdrant_search_billing_codes", "billing_codes", args, filters=args.get("filters"))


register_tool(
    "qdrant_search_billing_codes",
    {
        "description": "Search CPT/HCPCS/ICD-10 catalog for codes, descriptors, modifier rules.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "queries": {"type": "array", "items": {"type": "string"}, "description": "Several queries at once (one per code) — preferred over repeated calls; results come back per query."},
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
def _payload_of(hit: Any) -> dict:
    return (hit.get("payload") if isinstance(hit, dict) else getattr(hit, "payload", None)) or {}


def _valid_rule_hits(hits: list) -> list:
    """Contract gate at the retrieval seam (audit 2026-08-27 item 6): a stored rule that
    violates the schema (e.g. missing responsible_party) is logged and SKIPPED — the
    model never reasons from a rule the contract can't stand behind. Takes projected
    hit dicts or Hit objects."""
    from app.knowledge.rule_schema import validate_error_detection_rule

    valid = []
    for h in hits:
        payload = _payload_of(h)
        reasons = validate_error_detection_rule(payload)
        if reasons:
            rid = payload.get("rule_id") or (h.get("id") if isinstance(h, dict) else getattr(h, "id", None))
            log.warning("knowledge.invalid_rule_skipped", rule_id=str(rid), reasons=reasons)
            continue
        valid.append(h)
    return valid


async def _qdrant_search_error_detection_rules(args: dict[str, Any]) -> dict[str, Any]:
    out = await _run_search(
        "qdrant_search_error_detection_rules", "error_detection_rules", args, filters=args.get("filters")
    )
    if "error" in out:
        return out
    if "results" in out:
        for r in out["results"]:
            r["hits"] = _valid_rule_hits(r["hits"])
            r["count"] = len(r["hits"])
        out["count"] = sum(r["count"] for r in out["results"])
        return out
    out["hits"] = _valid_rule_hits(out["hits"])
    out["count"] = len(out["hits"])
    return out


register_tool(
    "qdrant_search_error_detection_rules",
    {
        "description": "Search Tyndale's curated error-detection rule library (the 23 checks + variants).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "queries": {"type": "array", "items": {"type": "string"}, "description": "Several queries at once (one per code) — preferred over repeated calls; results come back per query."},
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
    return await _run_search(
        "qdrant_search_laws_regulations", "laws_regulations", args,
        effective_date=args["effective_date"], filters=args.get("filters"),
    )


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
                "queries": {"type": "array", "items": {"type": "string"}, "description": "Several queries at once — one embedding call; results come back per query."},
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
    return await _run_search(
        "qdrant_search_payer_policies", "payer_policies", args,
        effective_date=args["effective_date"], filters=args.get("filters"),
    )


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
                "queries": {"type": "array", "items": {"type": "string"}, "description": "Several queries at once — one embedding call; results come back per query."},
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
