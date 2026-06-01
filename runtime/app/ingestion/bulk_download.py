"""Shared bulk-file downloader (Phase CO-3A).

Downloads large source files (CMS ZIPs, PFS files, hospital MRFs, TiC JSONL) and
stages them in BlobStorage. Features: HEAD-based size/Last-Modified probe,
idempotent skip when unchanged (sidecar .meta.json), resume-on-failure via Range
requests, per-host throttle + concurrency cap, descriptive User-Agent, robots
check. The httpx client + robots checker are injectable so tests drive it with an
httpx.MockTransport and no network.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from pydantic import BaseModel

from app.ingestion.blob_storage import BlobStorage

log = structlog.get_logger(__name__)

_USER_AGENT = (
    "TyndaleBot/1.0 (+https://tyndaleapp.net; medical-billing-advocacy; contact ops@tyndaleapp.net)"
)
_THROTTLE_SECONDS = 0.2
_PER_HOST_CONCURRENCY = 2
_CHUNK = 1 << 20  # 1 MiB
_host_sema: dict[str, asyncio.Semaphore] = {}


def _sema_for(url: str) -> asyncio.Semaphore:
    host = urlparse(url).netloc
    if host not in _host_sema:
        _host_sema[host] = asyncio.Semaphore(_PER_HOST_CONCURRENCY)
    return _host_sema[host]


def _default_robots_allow(url: str) -> bool:
    try:
        p = urlparse(url)
        rp = RobotFileParser()
        rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(_USER_AGENT, url)
    except Exception:  # noqa: BLE001 — robots unreachable -> permissive (still throttled)
        return True


@dataclass
class FileEntry:
    url: str
    filename: str
    size: int | None = None
    last_modified: str | None = None
    metadata: dict = field(default_factory=dict)


class DownloadResult(BaseModel):
    blob_path: str
    size_bytes: int
    last_modified: datetime.datetime | None = None
    sha256: str
    bytes_downloaded_this_run: int  # 0 == served from cache


class BulkDownloader:
    def __init__(
        self,
        blob: BlobStorage,
        *,
        client: httpx.AsyncClient | None = None,
        robots_allow: Callable[[str], bool] = _default_robots_allow,
        throttle_seconds: float = _THROTTLE_SECONDS,
    ) -> None:
        self._blob = blob
        self._client = client
        self._robots_allow = robots_allow
        self._throttle = throttle_seconds

    def _meta_path(self, blob_path: str) -> str:
        return f"{blob_path}.meta.json"

    async def _client_ctx(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, read=300.0), headers={"User-Agent": _USER_AGENT}
        )

    async def list_index(self, index_url: str) -> list[FileEntry]:
        """Fetch an index (HTML or JSON) and return the bulk files it points to."""
        if not self._robots_allow(index_url):
            raise PermissionError(f"robots.txt disallows {index_url}")
        client = await self._client_ctx()
        owns = self._client is None
        try:
            async with _sema_for(index_url):
                await asyncio.sleep(self._throttle)
                resp = await client.get(index_url, follow_redirects=True)
                resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            if "json" in ctype:
                return _entries_from_json(resp.json())
            return _entries_from_html(resp.text, index_url)
        finally:
            if owns:
                await client.aclose()

    async def download(
        self,
        source_url: str,
        blob_path: str,
        expected_size_mb: int | None = None,
        resumable: bool = True,
    ) -> DownloadResult:
        if not self._robots_allow(source_url):
            raise PermissionError(f"robots.txt disallows {source_url}")

        client = await self._client_ctx()
        owns = self._client is None
        try:
            head = await self._head(client, source_url)
            remote_lm = head.get("last_modified")

            # Idempotent skip: sidecar records the source Last-Modified we have.
            meta = await self._read_meta(blob_path)
            if meta and meta.get("last_modified") and meta.get("last_modified") == remote_lm:
                size = await self._blob.size(blob_path)
                return DownloadResult(
                    blob_path=blob_path,
                    size_bytes=size,
                    last_modified=_parse_http_date(remote_lm),
                    sha256=meta.get("sha256", ""),
                    bytes_downloaded_this_run=0,
                )

            # Resume: continue from however much we already have (Range).
            start = 0
            if resumable and head.get("accept_ranges") and await self._blob.exists(blob_path):
                start = await self._blob.size(blob_path)
                total = head.get("size")
                if total and start >= total:
                    start = 0  # already complete-but-no-sidecar: re-fetch to verify

            downloaded = await self._stream(client, source_url, blob_path, start)

            size = await self._blob.size(blob_path)
            sha = hashlib.sha256(await self._blob.read_bytes(blob_path)).hexdigest()
            await self._write_meta(
                blob_path, {"last_modified": remote_lm, "sha256": sha, "size": size}
            )
            return DownloadResult(
                blob_path=blob_path,
                size_bytes=size,
                last_modified=_parse_http_date(remote_lm),
                sha256=sha,
                bytes_downloaded_this_run=downloaded,
            )
        finally:
            if owns:
                await client.aclose()

    async def _head(self, client: httpx.AsyncClient, url: str) -> dict:
        async with _sema_for(url):
            await asyncio.sleep(self._throttle)
            resp = await client.head(url, follow_redirects=True)
        size = resp.headers.get("content-length")
        return {
            "size": int(size) if size and size.isdigit() else None,
            "last_modified": resp.headers.get("last-modified"),
            "accept_ranges": "bytes" in resp.headers.get("accept-ranges", "").lower(),
        }

    async def _stream(self, client: httpx.AsyncClient, url: str, blob_path: str, start: int) -> int:
        headers = {"Range": f"bytes={start}-"} if start > 0 else {}
        downloaded = 0
        async with _sema_for(url):
            await asyncio.sleep(self._throttle)
            async with client.stream("GET", url, headers=headers, follow_redirects=True) as resp:
                resp.raise_for_status()
                append = start > 0 and resp.status_code == 206  # partial content honored
                first = True
                async for chunk in resp.aiter_bytes(_CHUNK):
                    await self._blob.write_bytes(blob_path, chunk, append=append or not first)
                    first = False
                    downloaded += len(chunk)
        return downloaded

    async def _read_meta(self, blob_path: str) -> dict | None:
        mp = self._meta_path(blob_path)
        if not await self._blob.exists(mp):
            return None
        try:
            return json.loads((await self._blob.read_bytes(mp)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    async def _write_meta(self, blob_path: str, meta: dict) -> None:
        await self._blob.write_bytes(self._meta_path(blob_path), json.dumps(meta).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Index parsing
# --------------------------------------------------------------------------- #
_HREF_RE = re.compile(r'href=["\']([^"\']+\.(?:zip|csv|json|jsonl|gz|xlsx?))["\']', re.IGNORECASE)


def _entries_from_html(html: str, base_url: str) -> list[FileEntry]:
    base = urlparse(base_url)
    out: list[FileEntry] = []
    seen: set[str] = set()
    for href in _HREF_RE.findall(html):
        url = (
            href
            if href.startswith("http")
            else f"{base.scheme}://{base.netloc}{href if href.startswith('/') else '/' + href}"
        )
        if url in seen:
            continue
        seen.add(url)
        out.append(FileEntry(url=url, filename=url.rsplit("/", 1)[-1]))
    return out


def _entries_from_json(payload: object) -> list[FileEntry]:
    rows = (
        payload
        if isinstance(payload, list)
        else (payload.get("files") or payload.get("data") or [])
        if isinstance(payload, dict)
        else []
    )
    out: list[FileEntry] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        url = r.get("url") or r.get("location") or r.get("href")
        if not url:
            continue
        out.append(
            FileEntry(
                url=str(url),
                filename=str(r.get("filename") or str(url).rsplit("/", 1)[-1]),
                size=r.get("size"),
                last_modified=r.get("last_modified"),
                metadata={
                    k: v
                    for k, v in r.items()
                    if k not in ("url", "filename", "size", "last_modified")
                },
            )
        )
    return out


def _parse_http_date(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            return datetime.datetime.strptime(value, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    return None
