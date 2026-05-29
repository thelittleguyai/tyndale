"""Cost-estimation tools.

Both are V1-Lite shims:
- ``cost_estimate_medicare_rvu`` returns a hand-coded RVU benchmark for known
  CPTs (MRI brain w/ + w/o contrast = 70553) so the MRI walking-skeleton path
  has a plausible Tyndale-computed responsibility. Real RVU lookups (CMS
  PFS API or static table) land in Phase 5.
- ``cost_estimate_fair_health`` is left as a stub raising NotImplementedError
  — Brock's public-data pivot (Phase 2G) replaces it. Per the prompt,
  Math Person uses Medicare RVU as the V1-Lite path.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.tools import register_tool

log = structlog.get_logger(__name__)


# Hand-coded V1-Lite reference rates — replace with CMS PFS lookup in Phase 5.
_MEDICARE_BENCHMARK: dict[str, dict[str, float]] = {
    "70553": {  # MRI brain w/ + w/o contrast
        "national_avg_allowed": 560.0,
        "global_period_days": 0.0,
        "rvu_work": 2.29,
        "rvu_total": 19.28,
    },
}


async def _cost_estimate_medicare_rvu(args: dict[str, Any]) -> dict[str, Any]:
    cpt = str(args.get("cpt_code", "")).strip()
    if not cpt:
        return {"error": "cpt_code required"}
    bench = _MEDICARE_BENCHMARK.get(cpt)
    if bench is None:
        return {
            "cpt_code": cpt,
            "available": False,
            "note": "No V1-Lite benchmark for this CPT — Phase 5 wires the full RVU table.",
        }
    return {
        "cpt_code": cpt,
        "available": True,
        "benchmark": bench,
        "source": "V1-Lite hand-coded Medicare RVU reference (CMS PFS replacement in Phase 5)",
    }


register_tool(
    "cost_estimate_medicare_rvu",
    {
        "description": (
            "Look up a Medicare RVU-based benchmark for a CPT/HCPCS code. Used by Math Person "
            "to compute an independent fair-price reference. V1-Lite has a hand-coded table; "
            "Phase 5 ingests the full CMS PFS."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cpt_code": {"type": "string"},
            },
            "required": ["cpt_code"],
        },
    },
    _cost_estimate_medicare_rvu,
)


async def _cost_estimate_fair_health(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "error": "cost_estimate_fair_health is deferred — Phase 2G public-data pivot pending Brock's confirmation. Use cost_estimate_medicare_rvu instead.",
        "deferred": True,
    }


register_tool(
    "cost_estimate_fair_health",
    {
        "description": (
            "DEFERRED — public-data pivot pending Brock's confirmation (Phase 2G). "
            "Math Person should use cost_estimate_medicare_rvu instead in V1-Lite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"cpt_code": {"type": "string"}, "zip3": {"type": "string"}},
        },
    },
    _cost_estimate_fair_health,
)
