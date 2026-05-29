"""Pure-Python utility tools — date math, user notifications, complaint routing."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import structlog

from app.tools import register_tool

log = structlog.get_logger(__name__)


# --- deadline_calculate -----------------------------------------------------
async def _deadline_calculate(args: dict[str, Any]) -> dict[str, Any]:
    anchor_iso = args["anchor_date"]
    days = int(args["days"])
    business_days_only = bool(args.get("business_days_only", False))

    anchor = datetime.fromisoformat(anchor_iso.replace("Z", "+00:00")).date()
    if business_days_only:
        d = anchor
        added = 0
        while added < days:
            d += timedelta(days=1)
            if d.weekday() < 5:
                added += 1
        due = d
    else:
        due = anchor + timedelta(days=days)
    return {
        "anchor_date": anchor.isoformat(),
        "days_added": days,
        "business_days_only": business_days_only,
        "due_date": due.isoformat(),
    }


register_tool(
    "deadline_calculate",
    {
        "description": (
            "Compute a deadline (anchor_date + N [business] days). Used for appeal windows, "
            "EOB-receipt deadlines, payment-due dates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_date": {"type": "string", "description": "ISO date (the event the clock starts on)"},
                "days": {"type": "integer"},
                "business_days_only": {"type": "boolean", "default": False},
            },
            "required": ["anchor_date", "days"],
        },
    },
    _deadline_calculate,
)


# --- notify_user ------------------------------------------------------------
async def _notify_user(args: dict[str, Any]) -> dict[str, Any]:
    """V1-Lite: log-only. SMS/email lands in Phase 4 (SendGrid + Twilio)."""
    log.info(
        "notify_user.stub",
        user_id=args.get("user_id"),
        case_file_id=args.get("case_file_id"),
        channel=args.get("channel", "log"),
        message=args.get("message"),
    )
    return {
        "queued": False,
        "channel": "log",
        "note": "V1-Lite stub — real SMS/email sends are Phase 4 (SendGrid + Twilio + gated send approval).",
    }


register_tool(
    "notify_user",
    {
        "description": (
            "Notify the user about a deadline / status change. V1-Lite logs only; real SMS/email "
            "wires in Phase 4 with the gated send-approval flow."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "case_file_id": {"type": "string"},
                "channel": {"type": "string", "enum": ["sms", "email", "log"]},
                "message": {"type": "string"},
            },
            "required": ["user_id", "message"],
        },
    },
    _notify_user,
)


# --- legal_doi_complaint_route ----------------------------------------------
async def _legal_doi_complaint_route(args: dict[str, Any]) -> dict[str, Any]:
    """Return the State Department of Insurance complaint URL/contact for a state."""
    state = (args.get("state") or "").upper()
    # Minimal V1-Lite directory — Phase 5 ingests the full per-state table.
    directory = {
        "UT": {
            "agency": "Utah Insurance Department",
            "url": "https://insurance.utah.gov/consumers/file-a-complaint/",
            "phone": "1-801-957-9200",
        },
        "CA": {
            "agency": "California Department of Insurance",
            "url": "https://www.insurance.ca.gov/01-consumers/101-help/index.cfm",
            "phone": "1-800-927-4357",
        },
    }
    entry = directory.get(state)
    if entry is None:
        return {
            "state": state,
            "available": False,
            "note": "V1-Lite directory is partial (UT, CA). Phase 5 wires the full table — recommend the user search '<state> Department of Insurance file complaint'.",
        }
    return {"state": state, "available": True, **entry}


register_tool(
    "legal_doi_complaint_route",
    {
        "description": (
            "Look up the State Department of Insurance complaint-filing route for a state "
            "(URL + phone). V1-Lite directory is partial (UT, CA only)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Two-letter state code"},
            },
            "required": ["state"],
        },
    },
    _legal_doi_complaint_route,
)
