"""Blob storage for bulk-data staging (Phase CO-3A).

Azure Blob when AZURE_STORAGE_CONNECTION_STRING is set; otherwise the local
filesystem under bulk_local_dir (dev/CI/tests). The runtime already depends on
azure-storage-blob. Parsers consume files via materialize_local() so they can use
zipfile / csv / gzip with a real path regardless of backend.

Layout (blob_path keys):
  cms-mcd/{filename}            medicare-pfs/{year}/{filename}
  hospital-mrf/{hospital_id}/{filename}
  tic-mrf/{payer}/{filename}
"""

from __future__ import annotations

import datetime
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


@dataclass
class BlobProperties:
    size_bytes: int
    last_modified: datetime.datetime


class BlobStorage:
    """Backend-agnostic blob ops. Local FS in dev; Azure Blob in prod."""

    def __init__(self) -> None:
        s = get_settings()
        self._conn = s.azure_storage_connection_string
        self._container_name = s.azure_storage_bulk_container
        self._local_root = s.bulk_local_dir
        self._container = None  # lazy Azure container client

    @property
    def is_azure(self) -> bool:
        return bool(self._conn)

    # --- Azure helpers ------------------------------------------------------
    def _azure(self):
        if self._container is None:
            from azure.storage.blob import BlobServiceClient

            svc = BlobServiceClient.from_connection_string(self._conn)
            self._container = svc.get_container_client(self._container_name)
            try:
                self._container.create_container()
            except Exception:  # noqa: BLE001 — already exists
                pass
        return self._container

    # --- Local helpers ------------------------------------------------------
    def _local_path(self, blob_path: str) -> str:
        return os.path.join(self._local_root, blob_path)

    # --- Public API ---------------------------------------------------------
    async def exists(self, blob_path: str) -> bool:
        if self.is_azure:
            return self._azure().get_blob_client(blob_path).exists()
        return os.path.exists(self._local_path(blob_path))

    async def properties(self, blob_path: str) -> BlobProperties | None:
        if self.is_azure:
            bc = self._azure().get_blob_client(blob_path)
            if not bc.exists():
                return None
            p = bc.get_blob_properties()
            return BlobProperties(size_bytes=p.size, last_modified=p.last_modified)
        path = self._local_path(blob_path)
        if not os.path.exists(path):
            return None
        st = os.stat(path)
        return BlobProperties(
            size_bytes=st.st_size,
            last_modified=datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc),
        )

    async def size(self, blob_path: str) -> int:
        p = await self.properties(blob_path)
        return p.size_bytes if p else 0

    async def write_bytes(self, blob_path: str, data: bytes, *, append: bool = False) -> None:
        if self.is_azure:
            # Simplified: full overwrite (Azure block-blob append is staged-block
            # work; resume is exercised in local mode — see BulkDownloader).
            self._azure().get_blob_client(blob_path).upload_blob(data, overwrite=not append)
            return
        path = self._local_path(blob_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "ab" if append else "wb") as f:
            f.write(data)

    async def read_bytes(self, blob_path: str) -> bytes:
        if self.is_azure:
            return self._azure().get_blob_client(blob_path).download_blob().readall()
        with open(self._local_path(blob_path), "rb") as f:
            return f.read()

    async def materialize_local(self, blob_path: str) -> str:
        """Return a real local filesystem path for the blob (downloading from
        Azure to a temp file if needed). Parsers use this for zipfile/csv/gzip."""
        if not self.is_azure:
            return self._local_path(blob_path)
        tmp = os.path.join(
            tempfile.gettempdir(),
            "tyndale_blob_" + hashlib.sha256(blob_path.encode()).hexdigest()[:16],
        )
        with open(tmp, "wb") as f:
            self._azure().get_blob_client(blob_path).download_blob().readinto(f)
        return tmp

    async def put_local_file(self, local_path: str, blob_path: str) -> None:
        """Stage an existing local file into blob storage (test/seed helper)."""
        if self.is_azure:
            with open(local_path, "rb") as f:
                self._azure().get_blob_client(blob_path).upload_blob(f, overwrite=True)
            return
        dst = self._local_path(blob_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(local_path, dst)
