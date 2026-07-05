"""Nightly Qdrant snapshot -> Azure Blob (Phase 3.3).

The Azure Files volume already makes Qdrant durable across restarts; this adds a point-in-time
backup to the `qdrant-snapshots` blob container for disaster recovery (accidental collection
drop, corruption, a bad re-seed). Runs as a scheduled cron (`python -m app.crons qdrant_snapshot`).

Creates a full storage snapshot via Qdrant's REST API, streams it into blob storage, then deletes
the on-server copy to keep the volume lean. No-ops cleanly when Qdrant is in embedded/local mode.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from app.config import get_settings
from app.ingestion.blob_storage import BlobStorage
from app.knowledge.client import is_server_mode

log = structlog.get_logger(__name__)

_SNAPSHOTS_CONTAINER = "qdrant-snapshots"


async def run_qdrant_snapshot_cron() -> dict:
    settings = get_settings()
    if not is_server_mode():
        log.info(
            "cron.qdrant_snapshot.skipped", reason="qdrant not in server mode (local/embedded)"
        )
        return {"skipped": "qdrant not in server mode"}

    base = settings.qdrant_url.rstrip("/")
    headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}

    async with httpx.AsyncClient(timeout=600.0) as client:
        created = await client.post(f"{base}/snapshots", headers=headers)
        created.raise_for_status()
        name = created.json()["result"]["name"]
        log.info("cron.qdrant_snapshot.created", snapshot=name)

        downloaded = await client.get(f"{base}/snapshots/{name}", headers=headers)
        downloaded.raise_for_status()
        data = downloaded.content

    blob_ref = f"{datetime.now(timezone.utc):%Y/%m/%d}/{name}"
    await BlobStorage(container=_SNAPSHOTS_CONTAINER).write_bytes(blob_ref, data)
    log.info("cron.qdrant_snapshot.uploaded", blob_ref=blob_ref, bytes=len(data))

    # Free the on-server snapshot (best-effort — the backup is already in blob).
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.delete(f"{base}/snapshots/{name}", headers=headers)
    except Exception as exc:  # noqa: BLE001 — cleanup only; the blob backup is what matters
        log.warning("cron.qdrant_snapshot.server_cleanup_failed", snapshot=name, error=str(exc))

    return {"snapshot": name, "blob_ref": blob_ref, "bytes": len(data)}
