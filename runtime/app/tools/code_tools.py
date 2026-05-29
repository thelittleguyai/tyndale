"""NCCI / MUE code-pair tools — stubs for walking skeleton.

The real NCCI bundling and MUE tables get ingested into Postgres in Phase 5.
Until then, these return "no edit found" so the subagent flow doesn't break
on calls. This is also why these tools always return ``source: "stub"`` —
Math Person + Bill Detective MUST surface the stub-ness in any finding so
the user can be told the bundling check wasn't authoritative.
"""

from __future__ import annotations

from typing import Any

from app.tools import register_tool


async def _ncci_check_pair(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_cpt": args.get("primary_cpt"),
        "secondary_cpt": args.get("secondary_cpt"),
        "edit_found": False,
        "modifier_allowed": None,
        "source": "stub",
        "note": "NCCI bundling tables ingest in Phase 5 — Math Person/Bill Detective must surface this stub-ness in any finding.",
    }


register_tool(
    "ncci_check_pair",
    {
        "description": (
            "Check whether a CPT pair has an NCCI bundling edit. STUB in V1-Lite — "
            "always returns 'no edit found'; downstream consumers must note the stub."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "primary_cpt": {"type": "string"},
                "secondary_cpt": {"type": "string"},
            },
            "required": ["primary_cpt", "secondary_cpt"],
        },
    },
    _ncci_check_pair,
)


async def _mue_check(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "cpt_code": args.get("cpt_code"),
        "billed_units": args.get("billed_units"),
        "mue_threshold": None,
        "exceeds_threshold": False,
        "source": "stub",
        "note": "MUE table ingest in Phase 5.",
    }


register_tool(
    "mue_check",
    {
        "description": "Check whether billed units exceed the MUE threshold for a CPT. STUB in V1-Lite.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cpt_code": {"type": "string"},
                "billed_units": {"type": "integer"},
            },
            "required": ["cpt_code", "billed_units"],
        },
    },
    _mue_check,
)
