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


class _LocalWriter:
    def __init__(self, path: str, resume: bool) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, "ab" if resume else "wb")  # noqa: SIM115 — closed in close()

    async def write(self, chunk: bytes) -> None:
        self._f.write(chunk)

    async def close(self) -> None:
        self._f.close()


class _AzureBlockWriter:
    """A real APPEND on Azure (cms_ncd_lcd_bulk / hospital_mrf, e2e re-test 2026-09-23 item 6).

    Block blobs have no append. The old write_bytes(append=True) sent every chunk after the
    first as ``upload_blob(overwrite=False)`` onto the blob the first chunk had just created —
    ``BlobAlreadyExists`` on the second MiB of any file, every run since the bulk crons were
    scheduled. (``overwrite=True`` would not have fixed it: each chunk would have REPLACED the
    blob, leaving only the last MiB and a corrupt ZIP.) Each chunk is staged as a block and the
    block list committed every ``COMMIT_EVERY`` blocks and at close — so an interrupted
    download leaves a committed prefix the next run resumes from with a Range request, and the
    blob's previous content stays intact until the first commit replaces it."""

    COMMIT_EVERY = 32  # 32 × 1 MiB chunks

    def __init__(self, blob_client, committed_ids: list[str]) -> None:
        self._bc = blob_client
        self._ids = list(committed_ids)
        self._pending = 0
        self._wrote = False

    async def write(self, chunk: bytes) -> None:
        if not chunk:
            return
        import uuid

        block_id = uuid.uuid4().hex  # same length for every block of the blob, as Azure requires
        self._bc.stage_block(block_id=block_id, data=chunk)
        self._ids.append(block_id)
        self._pending += 1
        self._wrote = True
        if self._pending >= self.COMMIT_EVERY:
            self._commit()

    def _commit(self) -> None:
        from azure.storage.blob import BlobBlock

        self._bc.commit_block_list([BlobBlock(block_id=b) for b in self._ids])
        self._pending = 0

    async def close(self) -> None:
        if self._pending or not self._wrote:
            self._commit()  # an empty stream still leaves an (empty) blob, like a write would


class BlobStorage:
    """Backend-agnostic blob ops. Local FS in dev; Azure Blob in prod."""

    def __init__(self, container: str | None = None) -> None:
        s = get_settings()
        self._conn = s.azure_storage_connection_string
        # Default is the bulk-data staging container; callers storing other content
        # (e.g. insurance-card images -> the uploads container) pass one explicitly.
        self._container_name = container or s.azure_storage_bulk_container
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
        """Write a whole blob (idempotent: a rewrite replaces it), or ``append`` to one written
        through ``open_writer`` (Azure needs its block list — see _AzureBlockWriter)."""
        if self.is_azure and not append:
            self._azure().get_blob_client(blob_path).upload_blob(data, overwrite=True)
            return
        if self.is_azure:
            w = await self.open_writer(blob_path, resume=True)
            await w.write(data)
            await w.close()
            return
        path = self._local_path(blob_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "ab" if append else "wb") as f:
            f.write(data)

    async def appendable_size(self, blob_path: str) -> int:
        """How many bytes of the blob a streamed write can CONTINUE from. Locally, the file's
        size. On Azure, the committed blocks' total — 0 for a blob written whole (it has no
        block list to extend), so a resumed download starts over instead of corrupting it."""
        if not self.is_azure:
            path = self._local_path(blob_path)
            return os.path.getsize(path) if os.path.exists(path) else 0
        bc = self._azure().get_blob_client(blob_path)
        if not bc.exists():
            return 0
        committed, _ = bc.get_block_list("committed")
        return sum(int(b.size or 0) for b in committed or [])

    async def open_writer(self, blob_path: str, *, resume: bool = False):
        """A streamed writer: ``await w.write(chunk)`` … ``await w.close()``. ``resume`` continues
        the blob's existing content; otherwise the content is replaced (on Azure, at the first
        commit — until then the previous blob stays readable)."""
        if not self.is_azure:
            return _LocalWriter(self._local_path(blob_path), resume)
        bc = self._azure().get_blob_client(blob_path)
        committed_ids: list[str] = []
        if resume and bc.exists():
            committed, _ = bc.get_block_list("committed")
            committed_ids = [b.id for b in committed or []]
            appendable = sum(int(b.size or 0) for b in committed or [])
            if appendable != bc.get_blob_properties().size:
                raise ValueError(
                    f"{blob_path} was written whole and has no block list to append to — "
                    "rewrite it instead of resuming"
                )
        return _AzureBlockWriter(bc, committed_ids)

    async def read_bytes(self, blob_path: str) -> bytes:
        if self.is_azure:
            return self._azure().get_blob_client(blob_path).download_blob().readall()
        with open(self._local_path(blob_path), "rb") as f:
            return f.read()

    async def delete(self, blob_path: str) -> bool:
        """Delete a blob. Returns True if a blob was removed, False if it was already gone
        (idempotent — a missing blob is not an error, so an account-deletion scrub can be
        safely re-run). Used to purge insurance-card images on account deletion (CO-17)."""
        if self.is_azure:
            bc = self._azure().get_blob_client(blob_path)
            if not bc.exists():
                return False
            bc.delete_blob()
            return True
        path = self._local_path(blob_path)
        if not os.path.exists(path):
            return False
        os.remove(path)
        return True

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

    def signed_url(self, blob_path: str, minutes: int = 15) -> str | None:
        """A short-lived, read-only URL for the blob, or None when not on Azure
        (local dev/CI streams the bytes through the authed route instead). The URL
        is the blob path + a SAS token — PHI-free, never member data (CO-17 / DL-47)."""
        if not self.is_azure:
            return None
        from datetime import timedelta

        from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

        svc = BlobServiceClient.from_connection_string(self._conn)
        sas = generate_blob_sas(
            account_name=svc.account_name,
            container_name=self._container_name,
            blob_name=blob_path,
            account_key=svc.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.datetime.now(datetime.timezone.utc) + timedelta(minutes=minutes),
        )
        return f"{svc.get_blob_client(self._container_name, blob_path).url}?{sas}"
