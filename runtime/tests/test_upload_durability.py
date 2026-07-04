"""_persist (Phase 1.3): PHI uploads land durably in Blob or fail CLEAN with a 503 —
never a silent fall-back to the replica's ephemeral local disk (DL-47). Local disk is
allowed ONLY in local dev (no Blob configured, non-production)."""

from __future__ import annotations

import azure.storage.blob.aio as _blobaio
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.routes import upload


def _patch_settings(monkeypatch, **over) -> Settings:
    s = Settings(database_url="postgresql+asyncpg://u:p@localhost/db", **over)  # type: ignore[arg-type]
    monkeypatch.setattr(upload, "get_settings", lambda: s)
    return s


@pytest.mark.asyncio
async def test_blob_error_503_no_local_fallback(monkeypatch, tmp_path):
    # Blob is the configured store but the client fails → 503, and NOTHING is written locally.
    _patch_settings(
        monkeypatch,
        azure_storage_account_url="https://acct.blob.core.windows.net",
        azure_storage_uploads_container="uploads",
        local_uploads_dir=str(tmp_path),
    )

    def _boom(*a, **k):
        raise RuntimeError("blob unreachable RAWSECRET")

    monkeypatch.setattr(_blobaio, "BlobServiceClient", _boom)

    with pytest.raises(HTTPException) as ei:
        await upload._persist(b"PHI bytes", "bill.pdf")

    assert ei.value.status_code == 503
    assert "RAWSECRET" not in str(ei.value.detail)  # no raw provider text reaches the user
    assert not list(tmp_path.iterdir())  # no silent ephemeral fallback


@pytest.mark.asyncio
async def test_production_without_blob_503(monkeypatch, tmp_path):
    # Production with NO Blob configured is a misconfig — must 503, never write local.
    _patch_settings(
        monkeypatch,
        node_env="production",
        azure_storage_account_url=None,
        local_uploads_dir=str(tmp_path),
    )
    with pytest.raises(HTTPException) as ei:
        await upload._persist(b"PHI bytes", "bill.pdf")
    assert ei.value.status_code == 503
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_local_dev_without_blob_writes_local(monkeypatch, tmp_path):
    # Local dev (no Blob, not production) keeps the local-disk path.
    _patch_settings(
        monkeypatch,
        node_env="development",
        azure_storage_account_url=None,
        local_uploads_dir=str(tmp_path),
    )
    uri = await upload._persist(b"PHI bytes", "bill.pdf")
    assert uri.startswith(str(tmp_path))
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == b"PHI bytes"
