"""Cron registry (Phase CO-9, Module 5).

Maps cron name → callable + schedule metadata so the admin console can list every cron and
trigger one by name. Includes a 'noop' cron for pipeline smoke-tests.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.crons.cms_ncd_lcd_bulk_cron import run_cms_ncd_lcd_bulk_cron
from app.crons.hospital_mrf_cron import run_hospital_mrf_cron
from app.crons.medicare_pfs_cron import run_medicare_pfs_cron
from app.crons.outcome_followup import scan_for_outcome_followups
from app.crons.tic_mrf_cron import run_tic_mrf_cron

CronFn = Callable[[], Awaitable[Any]]


async def _noop_cron() -> dict:
    """Do-nothing cron — lets an admin verify the trigger → run-log pipeline safely."""
    return {"ok": True, "noop": True}


async def _outcome_followup_cron() -> dict:
    found = await scan_for_outcome_followups()
    return {"followups_found": len(found)}


CRON_REGISTRY: dict[str, dict[str, Any]] = {
    "cms_ncd_lcd_bulk": {"fn": run_cms_ncd_lcd_bulk_cron, "schedule": "weekly Sun 03:00 UTC"},
    "medicare_pfs": {"fn": run_medicare_pfs_cron, "schedule": "annual ~Jan 5"},
    "hospital_mrf": {"fn": run_hospital_mrf_cron, "schedule": "monthly first Sun"},
    "tic_mrf": {"fn": run_tic_mrf_cron, "schedule": "monthly"},
    "outcome_followup": {"fn": _outcome_followup_cron, "schedule": "daily"},
    "noop": {"fn": _noop_cron, "schedule": "manual"},
}


def list_crons() -> list[str]:
    return list(CRON_REGISTRY.keys())


def get_cron(name: str) -> CronFn | None:
    entry = CRON_REGISTRY.get(name)
    return entry["fn"] if entry else None
