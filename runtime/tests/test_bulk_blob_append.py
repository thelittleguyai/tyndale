"""The bulk crons can write a file bigger than 1 MiB to Azure (e2e re-test 2026-09-23, item 6).

cms_ncd_lcd_bulk (and hospital_mrf) failed on ``BlobAlreadyExists`` 3 s into every run: the
downloader wrote 1 MiB chunks, the first as ``upload_blob(overwrite=True)`` and every later one
as ``upload_blob(overwrite=False)`` onto the blob the first had just created. ``overwrite=True``
would have "fixed" the error and kept only the LAST MiB — a corrupt ZIP. A download is now ONE
streamed writer (staged blocks, committed as it goes), resumes only a prefix of the same source
version, and the run log records ``skipped_unchanged`` vs ``written``.
"""

from __future__ import annotations

import datetime

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.ingestion.blob_storage import BlobStorage, _AzureBlockWriter
from app.ingestion.bulk_download import BulkDownloader

MIB = 1 << 20


# ── a faithful-enough Azure block blob ──────────────────────────────────────────────────
class _Blk:
    def __init__(self, id, size):
        self.id, self.size = id, size


class _FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def _get(self):
        return self.store.blobs.get(self.name)

    def exists(self):
        return self.name in self.store.blobs

    def upload_blob(self, data, overwrite=False):
        self.store.calls.append(("upload_blob", self.name, overwrite))
        if not overwrite and self.exists():
            raise RuntimeError("BlobAlreadyExists")
        data = data.read() if hasattr(data, "read") else bytes(data)
        self.store.blobs[self.name] = {"data": data, "blocks": None}  # Put Blob: no block list

    def stage_block(self, block_id, data):
        self.store.staged.setdefault(self.name, {})[block_id] = bytes(data)

    def commit_block_list(self, blocks):
        prev = self._get() or {"blocks": []}
        known = {b: d for b, d in zip(prev.get("block_ids") or [], prev.get("block_data") or [])}
        staged = self.store.staged.get(self.name, {})
        ids = [b.id for b in blocks]
        data = [staged.get(i, known.get(i)) for i in ids]
        assert all(d is not None for d in data), "committed a block that was never staged"
        self.store.blobs[self.name] = {"data": b"".join(data), "blocks": True, "block_ids": ids, "block_data": data}
        self.store.calls.append(("commit", self.name, len(ids)))

    def get_block_list(self, _which="committed"):
        b = self._get()
        if not b or not b.get("blocks"):
            return [], []
        return [_Blk(i, len(d)) for i, d in zip(b["block_ids"], b["block_data"])], []

    def get_blob_properties(self):
        b = self._get()
        return type("P", (), {"size": len(b["data"]), "last_modified": datetime.datetime.now(datetime.timezone.utc)})()

    def download_blob(self):
        data = self._get()["data"]

        class _D:
            def readall(self_inner):
                return data

            def readinto(self_inner, f):
                f.write(data)

        return _D()


class _FakeContainer:
    def __init__(self):
        self.blobs, self.staged, self.calls = {}, {}, []

    def get_blob_client(self, name):
        return _FakeBlob(self, name)


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setattr(get_settings(), "azure_storage_connection_string", "DefaultEndpointsProtocol=https;fake")
    store = BlobStorage()
    container = _FakeContainer()
    monkeypatch.setattr(store, "_azure", lambda: container)
    return store, container


def _source(content: bytes, *, last_modified="Sun, 20 Sep 2026 03:00:00 GMT", fail_after: int | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-length": str(len(content)), "last-modified": last_modified, "accept-ranges": "bytes"})
        start = int(request.headers["range"].split("=")[1].split("-")[0]) if request.headers.get("range") else 0
        body = content[start:]
        if fail_after is not None:

            async def _broken():
                sent = 0
                for i in range(0, len(body), MIB):
                    if sent >= fail_after:
                        raise httpx.ReadError("connection reset mid-download")
                    yield body[i : i + MIB]
                    sent += 1

            return httpx.Response(206 if start else 200, content=_broken())
        return httpx.Response(206 if start else 200, content=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _bytes(n: int) -> bytes:
    return bytes((i * 7) % 251 for i in range(n))


# ── the bug, and the fix ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_multi_mib_download_lands_whole_on_azure(azure):
    store, container = azure
    content = _bytes(3 * MIB + 12345)
    res = await BulkDownloader(store, client=_source(content), robots_allow=lambda _u: True).download(
        "https://downloads.cms.gov/all_data.zip", "cms-mcd/all_data.zip"
    )
    assert await store.read_bytes("cms-mcd/all_data.zip") == content  # the whole file, not the last MiB
    assert res.outcome == "written" and res.bytes_downloaded_this_run == len(content)
    # the call that raised BlobAlreadyExists on the second MiB is gone for good
    assert not [c for c in container.calls if c[0] == "upload_blob" and c[1] == "cms-mcd/all_data.zip"]


@pytest.mark.asyncio
async def test_an_interrupted_download_resumes_from_what_was_committed(azure, monkeypatch):
    store, _ = azure
    monkeypatch.setattr(_AzureBlockWriter, "COMMIT_EVERY", 2)
    content = _bytes(5 * MIB + 99)
    dl = lambda client: BulkDownloader(store, client=client, robots_allow=lambda _u: True)  # noqa: E731
    with pytest.raises(httpx.ReadError):
        await dl(_source(content, fail_after=3)).download("https://x/all.zip", "cms-mcd/all.zip")
    kept = await store.appendable_size("cms-mcd/all.zip")
    assert 0 < kept < len(content) and kept % MIB == 0  # a committed prefix survived
    res = await dl(_source(content)).download("https://x/all.zip", "cms-mcd/all.zip")
    assert res.bytes_downloaded_this_run == len(content) - kept  # only the remainder
    assert await store.read_bytes("cms-mcd/all.zip") == content


@pytest.mark.asyncio
async def test_a_blob_written_whole_is_never_appended_to(azure):
    store, _ = azure
    await store.write_bytes("f.bin", b"whole")  # Put Blob — no block list
    assert await store.appendable_size("f.bin") == 0  # so a download starts over
    with pytest.raises(ValueError, match="no block list"):
        await store.open_writer("f.bin", resume=True)
    await store.write_bytes("f.bin", b"rewritten")  # and a whole rewrite is idempotent
    assert await store.read_bytes("f.bin") == b"rewritten"


# ── skipped_unchanged vs written ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_the_outcome_says_whether_anything_was_fetched_or_changed(azure):
    store, _ = azure
    body = _bytes(MIB + 7)
    lm1, lm2 = "Sun, 13 Sep 2026 03:00:00 GMT", "Sun, 20 Sep 2026 03:00:00 GMT"

    async def get(content, lm):
        return await BulkDownloader(store, client=_source(content, last_modified=lm), robots_allow=lambda _u: True).download(
            "https://x/a.zip", "cms-mcd/a.zip"
        )

    first = await get(body, lm1)
    assert (first.outcome, first.content_changed) == ("written", None)
    same = await get(body, lm1)
    assert (same.outcome, same.bytes_downloaded_this_run) == ("skipped_unchanged", 0)
    republished = await get(body, lm2)  # a new Last-Modified, the same bytes
    assert (republished.outcome, republished.content_changed) == ("written", False)
    changed = await get(body[:-1] + b"!", "Sun, 27 Sep 2026 03:00:00 GMT")
    assert (changed.outcome, changed.content_changed) == ("written", True)


@pytest.mark.asyncio
async def test_a_partial_of_another_version_is_not_resumed(azure):
    """A prefix of LAST week's file + a Range request on THIS week's = a corrupt mix."""
    store, _ = azure
    old, new = _bytes(2 * MIB), bytes(reversed(_bytes(2 * MIB)))
    w = await store.open_writer("cms-mcd/v.zip")
    await w.write(old[:MIB])
    await w.close()
    import json

    await store.write_bytes("cms-mcd/v.zip.meta.json", json.dumps({"partial_last_modified": "Sun, 13 Sep 2026 03:00:00 GMT"}).encode())
    res = await BulkDownloader(store, client=_source(new, last_modified="Sun, 20 Sep 2026 03:00:00 GMT"), robots_allow=lambda _u: True).download(
        "https://x/v.zip", "cms-mcd/v.zip"
    )
    assert res.bytes_downloaded_this_run == len(new)  # started over
    assert await store.read_bytes("cms-mcd/v.zip") == new


# ── the run log ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_voyage_refusing_every_embedding_stops_the_ingest_instead_of_outliving_the_job(monkeypatch, tmp_path):
    from app.ingestion import cms_ncd_lcd, chunk_policy
    from app.knowledge.embeddings import EmbeddingUnavailable

    monkeypatch.setattr(get_settings(), "azure_storage_connection_string", None)
    monkeypatch.setattr(get_settings(), "bulk_local_dir", str(tmp_path))
    calls = {"n": 0}

    async def _refused(_chunks):
        calls["n"] += 1
        raise EmbeddingUnavailable("voyage embeddings 429")

    monkeypatch.setattr(chunk_policy, "embed_and_upsert", _refused)

    class _Rec:
        def __init__(self, i):
            self.policy_id, self.policy_type = str(i), "ncd"

    async def _records(_self, _path, _blob):
        for i in range(20):
            yield _Rec(i)

    from app.ingestion.parsers import cms_mcd

    monkeypatch.setattr(cms_mcd.CmsMcdParser, "parse_file", _records)
    monkeypatch.setattr(cms_ncd_lcd, "_to_document", lambda rec: type("D", (), {"policy_id": rec.policy_id})())

    async def _extract(doc):
        return {}

    monkeypatch.setattr("app.ingestion.extract_policy.extract_policy", _extract)
    monkeypatch.setattr(chunk_policy, "chunk_policy", lambda extracted, doc: ["chunk"])
    report = await cms_ncd_lcd.ingest_from_bulk(blob_path="cms-mcd/local.zip", blob=BlobStorage(), sample_limit=250)
    assert report["stopped_early"] == "embeddings_unavailable"
    assert calls["n"] == cms_ncd_lcd.MAX_CONSECUTIVE_EMBED_OUTAGES == 3  # not 20, not 250


@pytest.mark.asyncio
async def test_a_run_whose_policies_failed_is_recorded_partial_not_success(monkeypatch):
    from app.crons import __main__ as cron_main
    from app.crons import cms_ncd_lcd_bulk_cron
    from app.db.base import AsyncSessionLocal
    from app.db.models.cron_run_log import CronRunLog

    async def _report(max_policies=None):
        return {"attempted": 3, "succeeded": 0, "failed": 3, "chunks_upserted": 0, "results": [],
                "download": {"outcome": "written", "bytes_downloaded": 5, "size_bytes": 5, "content_changed": None},
                "stopped_early": "embeddings_unavailable"}

    async def _audit(*_a, **_k):
        return None

    monkeypatch.setattr(cms_ncd_lcd_bulk_cron, "run_incremental_ingestion", _report)
    monkeypatch.setattr(cms_ncd_lcd_bulk_cron, "audit_cron_run", _audit)
    assert await cron_main.run_cron("cms_ncd_lcd_bulk") == 0  # partial is recorded, not retried
    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(CronRunLog).where(CronRunLog.cron_name == "cms_ncd_lcd_bulk").order_by(CronRunLog.started_at.desc()).limit(1)
        )).scalar_one()
    assert row.status == "partial"
    assert row.summary_json["download"]["outcome"] == "written"
    assert row.summary_json["stopped_early"] == "embeddings_unavailable"
