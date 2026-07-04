"""Shared cron helpers (Phase CO-3A) — audit every run + load the source data CSVs."""

from __future__ import annotations

import csv
import pathlib

from app.db.base import AsyncSessionLocal
from app.security.audit_writer import build_audit_event

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "ingestion" / "data"


async def audit_cron_run(actor: str, outcome: str, payload: dict, error: str | None = None) -> None:
    """Write one system_action audit row for a cron run, through the shared encrypted envelope."""
    async with AsyncSessionLocal() as s:
        s.add(
            build_audit_event(
                event_type="system_action",
                actor=actor,
                payload=payload,
                tools_invoked=["bulk_ingestion"],
                outcome=outcome,
                error_details=error,
            )
        )
        await s.commit()


def _load_csv(name: str) -> list[dict]:
    path = _DATA_DIR / name
    if not path.exists():
        return []
    out: list[dict] = []
    for row in csv.DictReader(
        line for line in path.read_text().splitlines() if not line.lstrip().startswith("#")
    ):
        out.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    return out


def load_top_100_hospitals() -> list[dict]:
    return _load_csv("top_100_hospitals.csv")


def load_tier1_payer_indices() -> list[dict]:
    return _load_csv("tier1_payer_tic_indices.csv")
