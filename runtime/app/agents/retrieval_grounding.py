"""Honest degradation when retrieval fails (e2e 2026-09-23 B1).

The specimen case (`36736626…`) ran with every knowledge tool erroring — 0 chunks retrieved —
and still shipped a [B]-tier legal claim ("required under ACA §2707 and PHSA §2707") with no
retrieved source behind it. Three things now happen instead, all from ONE record of what the
run actually retrieved (the agents' tool calls, the same material the Stop hook reads):

  1. the case carries a first-class ``retrieval`` record (research_log entry + the audit's
     provenance block) — calls, errors, chunks, and the verdict ok | degraded | unavailable;
  2. a legal claim whose citations resolve to NO retrieved chunk is DOWNGRADED — the finding
     stays (the observation is real) but as a [C] "worth checking" note, never a [B] claim;
  3. the user is told, in the registry's voice, that the rulebook was out of reach.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import cast, func, literal, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import bindparam

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile

log = structlog.get_logger(__name__)

KNOWLEDGE_TOOL_PREFIX = "qdrant_search_"
RETRIEVAL_ENTRY_KIND = "retrieval"
DOWNGRADE_REASON = "no_retrieved_source"
MAX_RECORDED_CHUNK_IDS = 200


# ── the record ─────────────────────────────────────────────────────────────────────────
def knowledge_calls(tool_calls: list[dict]) -> list[dict]:
    return [tc for tc in tool_calls if str(tc.get("name", "")).startswith(KNOWLEDGE_TOOL_PREFIX)]


def knowledge_chunks(tool_calls: list[dict]) -> list[dict]:
    """Every chunk the knowledge tools returned this run (single- and multi-query shapes)."""
    from app.agents.runner import _collect_retrieved_chunks

    calls = knowledge_calls(tool_calls)
    chunks = _collect_retrieved_chunks(calls)
    for tc in calls:  # the batched shape: {"results": [{"query", "hits": [...]}, ...]}
        result = tc.get("result")
        if isinstance(result, dict) and isinstance(result.get("results"), list):
            chunks.extend(_collect_retrieved_chunks([{"result": r} for r in result["results"] if isinstance(r, dict)]))
    return chunks


def retrieval_record(tool_calls: list[dict]) -> dict[str, Any]:
    """What this run retrieved, from the agents' tool calls. ``status``:
    ok (no knowledge-tool errors) · degraded (some errors, some chunks) ·
    unavailable (every knowledge call failed, or none returned a chunk while any failed)."""
    knowledge = knowledge_calls(tool_calls)
    errors = [tc for tc in knowledge if isinstance(tc.get("result"), dict) and "error" in tc["result"]]
    chunks = knowledge_chunks(knowledge)
    ids = sorted({str(c.get("id")) for c in chunks if c.get("id") is not None})
    if not knowledge or not errors:
        status = "ok"
    elif not chunks:
        status = "unavailable"
    else:
        status = "degraded"
    reasons = sorted({str((tc.get("result") or {}).get("error"))[:80] for tc in errors})
    return {
        "kind": RETRIEVAL_ENTRY_KIND,
        "status": status,
        "calls": len(knowledge),
        "errors": len(errors),
        "chunks": len(chunks),
        "chunk_ids": ids[:MAX_RECORDED_CHUNK_IDS],
        "error_reasons": reasons[:5],
        "at": datetime.now(timezone.utc).isoformat(),
    }


async def record_retrieval_on_case(case_file_id: str, record: dict[str, Any]) -> None:
    """The first-class flag on the case: ONE atomic research_log append (like tripwires).
    Never raises — a record that can't be written must not fail the audit it describes."""
    entry = {k: v for k, v in record.items() if k != "chunk_ids"}
    entry["chunk_ids"] = list(record.get("chunk_ids") or [])
    stmt = (
        update(CaseFile)
        .where(CaseFile.case_file_id == UUID(case_file_id))
        .values(
            research_log=func.coalesce(CaseFile.research_log, cast(literal("[]"), JSONB)).op("||")(
                bindparam("retrieval_entry", value=[entry], type_=JSONB)
            )
        )
    )
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(stmt)
            await s.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("retrieval.record_failed", case_file_id=case_file_id, error=str(exc))


def retrieval_entry(case: Any) -> dict[str, Any] | None:
    """The most recent retrieval record on a case (the last run wins), or None."""
    entries = [
        e for e in (getattr(case, "research_log", None) or [])
        if isinstance(e, dict) and e.get("kind") == RETRIEVAL_ENTRY_KIND
    ]
    return entries[-1] if entries else None


def retrieval_unavailable(case: Any) -> bool:
    entry = retrieval_entry(case)
    return bool(entry and entry.get("status") == "unavailable")


# ── legal-claim grounding ──────────────────────────────────────────────────────────────
_SECTION_RE = re.compile(r"§\s*([0-9][0-9a-zA-Z().-]*)")


def _chunk_index(chunks: list[dict]) -> tuple[set[str], str]:
    """(ids, haystack): every id a retrieved chunk answers to, and the chunks' own
    authority text (authority / citation / title / section fields) for a textual match."""
    ids: set[str] = set()
    text_parts: list[str] = []
    for c in chunks:
        for key in ("source_id", "src_id", "id", "chunk_id", "point_id"):
            v = c.get(key)
            if v is not None and str(v).strip():
                ids.add(str(v).strip())
        for key in ("authority", "citation", "title", "section", "source", "statute", "regulation", "rule_id"):
            v = c.get(key)
            if isinstance(v, str) and v.strip():
                text_parts.append(v.strip().upper())
    return ids, "\n".join(text_parts)


def _citation_resolves(citation: dict, ids: set[str], haystack: str) -> bool:
    for key in ("src_id", "source_id", "id", "chunk_id"):
        v = citation.get(key)
        if v is not None and str(v).strip() in ids:
            return True
    authority = str(citation.get("authority") or citation.get("source") or "").strip().upper()
    section = str(citation.get("section") or "").strip().upper()
    if authority and haystack:
        # the authority by name, and — when it names a section — that section too
        if authority in haystack and (not section or section in haystack):
            return True
        m = _SECTION_RE.search(authority)
        if m and m.group(1).upper() in haystack:
            return True
    return False


def legal_claim_has_substance(legal_claim: Any) -> bool:
    if not isinstance(legal_claim, dict) or legal_claim.get("downgraded"):
        return False
    return any(isinstance(v, str) and v.strip() for k, v in legal_claim.items() if k != "citations") or bool(
        legal_claim.get("citations")
    )


def downgrade_legal_claim(legal_claim: dict, reason: str = DOWNGRADE_REASON) -> dict:
    """The [B] claim, kept for the reviewer under ``unsourced``, no longer a claim: readers
    (``grounding.finding_tier`` / ``resolve_source``) treat a downgraded legal_claim as
    absent, the client never sees ``claim`` at the top level, and the citations that did
    not resolve are recorded as written — not rendered."""
    original = {k: v for k, v in legal_claim.items() if k != "citations"}
    return {
        "downgraded": reason,
        "unsourced": original,
        "citations_as_written": list(legal_claim.get("citations") or []),
    }


async def ground_legal_claims(case_file_id: str, chunks: list[dict]) -> list[str]:
    """Downgrade every finding whose legal claim resolves to no retrieved chunk. Returns the
    categories downgraded (for the tripwire + the log). A finding with no legal claim is
    untouched; a claim with at least one citation that resolves — by id, or by the authority
    (and section) appearing in a retrieved chunk's own authority text — stands."""
    from sqlalchemy import select

    from app.agents.context_loader import DOCTRINE_VIOLATIONS, orchestration_step
    from app.db.models.findings import Finding

    ids, haystack = _chunk_index(chunks)
    downgraded: list[str] = []
    async with AsyncSessionLocal() as s:
        rows = (
            (await s.execute(select(Finding).where(Finding.case_file_id == UUID(case_file_id))))
            .scalars()
            .all()
        )
        for f in rows:
            lc = f.legal_claim if isinstance(f.legal_claim, dict) else None
            if not legal_claim_has_substance(lc):
                continue
            citations = [c for c in (lc.get("citations") or []) if isinstance(c, dict)]
            if any(_citation_resolves(c, ids, haystack) for c in citations):
                continue
            DOCTRINE_VIOLATIONS[f"uncited_b_claim:{f.category}"] += 1
            log.warning(
                "orchestrator.legal_claim_downgraded",
                case_file_id=case_file_id,
                category=f.category,
                citations_as_written=[str(c.get("authority") or c.get("src_id") or "?")[:60] for c in citations],
                retrieved_chunks=len(chunks),
            )
            f.legal_claim = downgrade_legal_claim(lc)
            f.voice_tier = "C"
            rec = dict(f.recommendation) if isinstance(f.recommendation, dict) else {}
            note = orchestration_step("finding.worth_checking")
            if note and not note.startswith("<MISSING"):
                rec["worth_checking"] = note
            f.recommendation = rec
            downgraded.append(f.category)
        await s.commit()
    return downgraded
