"""One-shot backfill for case_files.provider_name + date_of_service (2026-07-15).

Fills the typed fields for EXISTING cases from STRUCTURED extraction artifacts only — the typed
field a newer upload already wrote, else the document's OCR preview (a document-level field), else
the EOB payload. It NEVER regexes the provider out of finding prose, and leaves the field null when
no structured source exists (the Record row's fallback title is correct there).

Usage: uv run python scripts/backfill_provider_name.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/ on the path

from sqlalchemy import select  # noqa: E402

from app.db.base import AsyncSessionLocal  # noqa: E402
from app.db.models.case_files import CaseFile  # noqa: E402
from app.sources.extraction import _grep_date, grep_provider_name  # noqa: E402

_DOS_ANCHORS = ("DATE OF SERVICE", "SERVICE DATE", "DOS")


def _eob_field(eobs, key: str) -> str | None:
    for e in eobs or []:
        if isinstance(e, dict):
            v = e.get(key) or (e.get("eob") or {}).get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def derive_provider_and_dos(case) -> tuple[str | None, datetime.date | None]:
    """(provider_name, date_of_service) from a case's STRUCTURED artifacts, or (None, None)."""
    docs = [d for d in (case.documents or []) if isinstance(d, dict)]

    provider = next((d["provider_name"] for d in docs if d.get("provider_name")), None)
    if provider is None:
        provider = next(
            (p for d in docs if (p := grep_provider_name(d.get("ocr_text_preview") or ""))), None
        )
    if provider is None:
        provider = _eob_field(case.eobs, "provider") or _eob_field(case.eobs, "provider_name")

    dos_raw = next((d["date_of_service"] for d in docs if d.get("date_of_service")), None)
    if dos_raw is None:
        dos_raw = next(
            (dd for d in docs if (dd := _grep_date(d.get("ocr_text_preview") or "", _DOS_ANCHORS))),
            None,
        )
    if dos_raw is None:
        dos_raw = _eob_field(case.eobs, "date_of_service")

    dos: datetime.date | None = None
    if dos_raw:
        try:
            dos = datetime.date.fromisoformat(str(dos_raw)[:10])
        except ValueError:
            dos = None
    return provider, dos


async def run_backfill(dry_run: bool = False) -> dict[str, int]:
    filled_p = filled_d = scanned = 0
    async with AsyncSessionLocal() as s:
        cases = (await s.execute(select(CaseFile))).scalars().all()
        for case in cases:
            scanned += 1
            if case.provider_name is not None and case.date_of_service is not None:
                continue
            provider, dos = derive_provider_and_dos(case)
            if case.provider_name is None and provider:
                case.provider_name = provider
                filled_p += 1
            if case.date_of_service is None and dos:
                case.date_of_service = dos
                filled_d += 1
        if not dry_run:
            await s.commit()
    return {"scanned": scanned, "provider_filled": filled_p, "date_filled": filled_d}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = asyncio.run(run_backfill(dry_run=args.dry_run))
    print(f"backfill: {result}")
