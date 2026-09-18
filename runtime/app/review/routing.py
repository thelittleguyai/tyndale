"""The disapproval-cause seam for Phase 2 (doc 39 §7-2b, Brock 2026-09-17).

Phase 1 STORES the cause on the verdict row (admin_verdicts.cause) and nothing else. This
module is the typed contract Phase 2 plugs into: each cause already maps to the kind of
follow-up it will produce, so the router, the rule-candidate writer and the eval-stub writer
can be added without touching the verdict endpoint or the schema.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

Cause = Literal["content_gap", "reasoning_error", "bad_input", "stale_data_source"]
CAUSES: tuple[str, ...] = ("content_gap", "reasoning_error", "bad_input", "stale_data_source")


class RouteTarget(str, Enum):
    """Where a disapproval goes in Phase 2 — by cause, never by note text."""

    RULE_CANDIDATE = "rule_candidate"  # content_gap → a rules/corpus authoring candidate (Brock)
    EVAL_CASE = "eval_case"  # reasoning_error → a doctrine eval stub from the case's facts
    INTAKE_GUARD = "intake_guard"  # bad_input → an extraction/intake guard candidate
    SOURCE_REFRESH = "source_refresh"  # stale_data_source → a data-source refresh item


_ROUTES: dict[str, RouteTarget] = {
    "content_gap": RouteTarget.RULE_CANDIDATE,
    "reasoning_error": RouteTarget.EVAL_CASE,
    "bad_input": RouteTarget.INTAKE_GUARD,
    "stale_data_source": RouteTarget.SOURCE_REFRESH,
}


def route_for(cause: str) -> RouteTarget:
    """The Phase 2 destination for a stored cause. Raises on an unknown cause so a schema
    drift can't silently route to nothing."""
    return _ROUTES[cause]


def route_verdict(*, cause: str | None) -> RouteTarget | None:
    """Phase 1 no-op: returns the target the verdict WOULD route to (None for approve /
    cant_verify), records nothing. Phase 2 replaces the body, not the signature."""
    return route_for(cause) if cause else None
