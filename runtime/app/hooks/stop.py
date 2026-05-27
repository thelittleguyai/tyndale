"""Stop hook — citation Layer-2 resolution (Phase 1C functional stub).

Parses citation markers of the form `[authority §section, src_id]` from the
generated output and verifies each src_id resolves to a retrieved chunk. This is
real logic (not a no-op); the security spine may extend it in Phase 4.
"""

from __future__ import annotations

import re

from app.hooks.contracts import StopInput, StopResult

# Matches e.g. "[ERISA §503, src_a8f3e7]" — captures authority and the src_id.
_CITATION_RE = re.compile(r"\[\s*([^\],]+?)\s*,\s*(src_[0-9a-fA-F]+)\s*\]")


def _chunk_ids(chunks: list[dict]) -> set[str]:
    ids: set[str] = set()
    for chunk in chunks:
        sid = chunk.get("source_id") or chunk.get("src_id") or chunk.get("id")
        if sid:
            ids.add(str(sid))
    return ids


def stop_hook(inp: StopInput) -> StopResult:
    markers = _CITATION_RE.findall(inp.generated_output)
    available = _chunk_ids(inp.retrieved_chunks)
    unresolved = [f"{authority} ({src_id})" for authority, src_id in markers if src_id not in available]

    if not unresolved:
        return StopResult(resolved=True, unresolved_citations=[], action="ship")

    action = "regenerate" if inp.attempt < 3 else "human_review"
    return StopResult(resolved=False, unresolved_citations=unresolved, action=action)
