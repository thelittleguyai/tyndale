"""Dev-only fault injection for the e2e harness (e2e re-test 2026-09-23, item 1).

"A transient 429 on the summary call must not end an audit" is only proven when the REAL
pipeline — the deployed runtime, the real agents, the real thread projection — sees a 429
where the summary is written. The harness asks for that with one header on the upload that
opens the case:

    X-Tyndale-Fault: claude_429:lead_planner

and the case carries the fault from then on. Three independent gates, the same belt and
suspenders as the test-token route (routes/admin/test_support.py):

  * NOT staging / production — the header is ignored there, full stop;
  * a SYNTHETIC user only (the e2e suffix) — a real person's case can never carry one;
  * a KNOWN fault name only — anything else is ignored and logged.

The fault is recorded in the case's research_log (``kind: "fault_injection"``), so the
admin case view shows why a synthetic run behaved the way it did, and it is scoped to ONE
stage of the FIRST run: the summary retry (crons/audit_retry) runs clean, so the harness can
also watch the recovery happen.
"""

from __future__ import annotations

import datetime
from contextlib import contextmanager
from typing import Any

import structlog

log = structlog.get_logger(__name__)

FAULT_HEADER = "X-Tyndale-Fault"
# fault name -> the agent stage it applies to
KNOWN_FAULTS: dict[str, str] = {
    "claude_429:lead_planner": "lead_planner",
}


def accepted_fault(value: str | None, *, user_email: str | None) -> str | None:
    """The fault to record for this upload, or None. Never raises."""
    if not value:
        return None
    from app.config import get_settings
    from app.notify.email import is_synthetic_email

    name = value.strip().lower()
    if get_settings().is_staging_or_prod:
        log.warning("faults.refused", reason="environment")
        return None
    if not is_synthetic_email(user_email):
        log.warning("faults.refused", reason="not_a_synthetic_user")
        return None
    if name not in KNOWN_FAULTS:
        log.warning("faults.refused", reason="unknown_fault")
        return None
    return name


def fault_entry(name: str) -> dict[str, Any]:
    return {
        "kind": "fault_injection",
        "fault": name,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


async def record_fault(session: Any, case_file_id: Any, name: str) -> None:
    """Append the fault to the case's research_log through the ONE atomic ``||`` UPDATE every
    research_log writer uses (never a read-modify-write — test_summary_tripwires guards it)."""
    from sqlalchemy import bindparam, cast, func, literal, update
    from sqlalchemy.dialects.postgresql import JSONB

    from app.db.models.case_files import CaseFile

    await session.execute(
        update(CaseFile)
        .where(CaseFile.case_file_id == case_file_id)
        .values(
            research_log=func.coalesce(CaseFile.research_log, cast(literal("[]"), JSONB)).op("||")(
                bindparam("fault_entry", value=[fault_entry(name)], type_=JSONB)
            )
        )
    )
    log.warning("faults.recorded", fault=name)


def case_faults(case: Any) -> set[str]:
    return {
        str(e.get("fault"))
        for e in (getattr(case, "research_log", None) or [])
        if isinstance(e, dict) and e.get("kind") == "fault_injection" and e.get("fault")
    }


@contextmanager
def injected(faults: set[str], stage: str):
    """While active, a Claude call on ``stage`` gets a synthesized 429 (see claude_retry)."""
    from app.agents.claude_retry import FAULT

    wanted = any(KNOWN_FAULTS.get(f) == stage and f.startswith("claude_429") for f in faults)
    token = FAULT.set("rate_limit") if wanted else None
    if wanted:
        log.warning("faults.injecting", stage=stage, fault="claude_429")
    try:
        yield wanted
    finally:
        if token is not None:
            FAULT.reset(token)
