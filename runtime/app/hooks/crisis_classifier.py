"""Crisis classifier — STUB (Phase 1C).

Returns crisis_detected=False unconditionally. TODO(Phase 4): wire the Haiku 4.5
classifier. Per DL-04 a positive signal triggers the Category-2 clean decline
(no 988, no routing), bypassing the Lead Planner.
"""

from __future__ import annotations

from app.hooks.contracts import CrisisClassifierInput, CrisisClassifierResult


def crisis_classifier(inp: CrisisClassifierInput) -> CrisisClassifierResult:
    return CrisisClassifierResult(crisis_detected=False)
