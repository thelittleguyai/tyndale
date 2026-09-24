"""Admin › Knowledge — the payer-instructions corpus ("Help me find it") and its re-verify clock.

The portal guide's own rule: re-verify quarterly, because portals change. This lists every entry
— a verified one with the day it was checked, the day its next check is due, and its steps exactly
as a member sees them; an unverified one with what the hands-on pass (test accounts) still has to
fill, which no member ever sees. Read-only: nothing here changes what users are shown.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.auth import CurrentUser
from app.intake.payer_instructions import (
    CORPUS,
    GUIDE,
    PAYER_ENTRIES,
    PAYERS,
    REVERIFY_EVERY_MONTHS,
    PayerEntry,
    reverify_due,
)
from app.intake.render import step
from app.routes.admin._deps import admin_user

router = APIRouter(tags=["v1-admin"])


def _row(e: PayerEntry, today: str) -> dict[str, Any]:
    due = reverify_due(e.verified_on) if e.verified else None
    # what a member sees — verbatim dock text, or the registry lines; nothing for an unverified one
    shown = (list(e.steps) or [t for k in e.step_keys if (t := step(k))]) if e.verified else []
    return {
        "document_type": e.document_type,
        "screen_id": e.screen_id,
        "verified": e.verified,
        "verified_on": e.verified_on,
        "due_on": due,
        "overdue": bool(due and due <= today),
        "source": e.source,
        "claim": e.claim,
        "steps": shown,
        "origin": "portal_guide" if e in CORPUS else "receiving_dock",
    }


@router.get("/admin/knowledge/payer-instructions")
async def payer_instructions(admin: CurrentUser = Depends(admin_user)) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    entries = list(CORPUS) + [e for e in PAYER_ENTRIES.values() if e not in CORPUS]
    by_payer: dict[str, list[dict]] = {}
    for e in entries:
        by_payer.setdefault(e.payer_id, []).append(_row(e, today))
    names = {pid: p.name for pid, p in PAYERS.items()}
    names.update({e.payer_id: e.payer_name for e in entries if e.payer_id not in names})
    rows = [r for rs in by_payer.values() for r in rs]
    dues = sorted(r["due_on"] for r in rows if r["due_on"])
    return {
        "source": GUIDE,
        "reverify_every_months": REVERIFY_EVERY_MONTHS,
        "today": today,
        "next_due": dues[0] if dues else None,
        "overdue": sum(1 for r in rows if r["overdue"]),
        "verified": sum(1 for r in rows if r["verified"]),
        "unverified": sum(1 for r in rows if not r["verified"]),
        "payers": [
            {"payer_id": pid, "name": names[pid], "entries": rs} for pid, rs in by_payer.items()
        ],
    }
