"""CLI entrypoint to run ONE registered cron by name — the command the scheduled Azure
Container Apps Jobs invoke: ``python -m app.crons <cron_name>``.

Records a CronRunLog row (triggered_source='scheduled') so the admin console's real last-run
state reflects scheduled executions exactly like manual admin triggers. Logs to stdout/stderr
(the job captures these). Exits 0 on success, 1 on failure/usage error, so the Container Apps
platform marks the execution Succeeded/Failed.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

import structlog

from app.crons.registry import get_cron, list_crons
from app.db.base import AsyncSessionLocal
from app.db.models.cron_run_log import CronRunLog

log = structlog.get_logger(__name__)


async def run_cron(cron_name: str) -> int:
    """Run one cron by name, recording start + outcome to CronRunLog. Returns a process exit code."""
    fn = get_cron(cron_name)
    if fn is None:
        print(
            f"Unknown cron '{cron_name}'. Available: {', '.join(list_crons())}",
            file=sys.stderr,
        )
        return 1

    async with AsyncSessionLocal() as s:
        row = CronRunLog(cron_name=cron_name, status="running", triggered_source="scheduled")
        s.add(row)
        await s.flush()
        run_id = row.run_id
        await s.commit()

    log.info("cron.scheduled.start", cron_name=cron_name, run_id=str(run_id))
    status: str = "success"
    error: str | None = None
    summary: dict | None = None
    try:
        result = await fn()
        summary = result if isinstance(result, dict) else {"result": str(result)}
    except Exception as exc:  # noqa: BLE001 — record the failure + exit non-zero
        status, error = "failed", str(exc)
        log.error("cron.scheduled.failed", cron_name=cron_name, run_id=str(run_id), error=error)

    async with AsyncSessionLocal() as s:
        row = await s.get(CronRunLog, run_id)
        if row is not None:
            row.finished_at = datetime.now(timezone.utc)
            row.status = status
            row.summary_json = summary
            row.error_message = error
            await s.commit()

    log.info("cron.scheduled.done", cron_name=cron_name, run_id=str(run_id), status=status)
    return 0 if status == "success" else 1


def main() -> int:
    if len(sys.argv) != 2:
        print(
            f"Usage: python -m app.crons <cron_name>\nAvailable: {', '.join(list_crons())}",
            file=sys.stderr,
        )
        return 1
    return asyncio.run(run_cron(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
