"""Backfill analytics_daily from source tables (Internal Analytics P0, §2).

Derives the flagship metrics (uploads, win rate, audit completion, needs-documents) for a date
range from the pre-instrumentation source tables (case_files, feedback_events) so the dashboard
isn't empty on day one. Backfilled rows are flagged ``backfilled=True``; once the live rollup runs
over a day that has real events, it overwrites the row (flag flips to False).

Usage:
  uv run python scripts/backfill_analytics.py 2026-06-01 2026-07-14
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/ on the path


def _date(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


async def _main() -> None:
    from app.analytics.rollup import run_backfill

    ap = argparse.ArgumentParser(description="Backfill analytics_daily from source tables")
    ap.add_argument("start", type=_date, help="first day (YYYY-MM-DD), inclusive")
    ap.add_argument("end", type=_date, help="last day (YYYY-MM-DD), inclusive")
    args = ap.parse_args()
    result = await run_backfill(args.start, args.end)
    print(result)


if __name__ == "__main__":
    asyncio.run(_main())
