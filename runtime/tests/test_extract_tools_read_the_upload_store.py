"""The audit-phase extract tools read the SAME store the upload wrote to (e2e 2026-09-23 M3).

`upload_extract_eob` / `upload_extract_coverage` are handed the document's `uri` as
`file_path`. On dev that is a Blob URL — and the tool opened it as a local file
(`FileNotFoundError: 'https://…blob.core.windows.net/uploads/…eob.pdf'`), so coverage and EOB
re-extraction silently degraded. Both stores now go through `read_stored`; an http(s) URL that
is not our store is refused (never an arbitrary fetch); a plain local path still opens.
"""

from __future__ import annotations

import asyncio
import base64

import pytest

from app.config import get_settings
from app.sources import extraction


@pytest.mark.asyncio
async def test_a_blob_uri_is_read_through_the_upload_store_not_the_local_disk(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "azure_storage_account_url", "https://tyndaledev.blob.core.windows.net")
    monkeypatch.setattr(s, "azure_storage_uploads_container", "uploads")
    monkeypatch.setattr(s, "use_real_ocr", False)
    uri = "https://tyndaledev.blob.core.windows.net/uploads/abc_eob.pdf"
    calls: list[str] = []

    async def fake_read_stored(u):
        calls.append(u)
        return b"%PDF-1.4 EXPLANATION OF BENEFITS" if u == uri else None

    from app.routes import upload as upload_route

    monkeypatch.setattr(upload_route, "read_stored", fake_read_stored)
    data, name = await extraction._read_bytes({"file_path": uri})
    assert data.startswith(b"%PDF") and name == "abc_eob.pdf" and calls == [uri]
    # the full tool path: run_document_ocr no longer raises FileNotFoundError on a Blob URL
    r = await extraction.run_document_ocr({"file_path": uri})
    assert r["filename"] == "abc_eob.pdf" and r.get("ocr_text") is not None

    # a URL that is NOT our store is refused — a tool never fetches an arbitrary URL
    with pytest.raises(ValueError, match="not in this environment's upload store"):
        await extraction._read_bytes({"file_path": "https://example.com/anything.pdf"})


@pytest.mark.asyncio
async def test_local_dev_reads_the_disk_store_and_a_plain_path_still_opens(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "azure_storage_account_url", None)
    monkeypatch.setattr(s, "local_uploads_dir", str(tmp_path))
    stored = tmp_path / "x_bill.pdf"
    stored.write_bytes(b"%PDF-1.4 STATEMENT")
    data, name = await extraction._read_bytes({"file_path": str(stored)})  # inside the disk store
    assert data == b"%PDF-1.4 STATEMENT" and name == "x_bill.pdf"
    elsewhere = tmp_path.parent / f"{tmp_path.name}_fixture.pdf"
    elsewhere.write_bytes(b"%PDF-1.4 FIXTURE")
    data, _ = await extraction._read_bytes({"file_path": str(elsewhere)})  # a plain local path (fixtures)
    assert data == b"%PDF-1.4 FIXTURE"
    elsewhere.unlink()
    # base64 unchanged
    data, name = await extraction._read_bytes({"content_base64": base64.b64encode(b"hi").decode(), "filename": "c.png"})
    assert data == b"hi" and name == "c.png"


def test_the_tool_error_is_typed_not_a_traceback(monkeypatch):
    """A missing stored document is ONE clear reason in the tool result, not FileNotFoundError."""
    s = get_settings()
    monkeypatch.setattr(s, "azure_storage_account_url", "https://tyndaledev.blob.core.windows.net")
    monkeypatch.setattr(s, "azure_storage_uploads_container", "uploads")

    async def none(_u):
        return None

    from app.routes import upload as upload_route

    monkeypatch.setattr(upload_route, "read_stored", none)
    from app.tools import call_tool

    out = asyncio.run(call_tool("upload_extract_eob", {"file_path": "https://tyndaledev.blob.core.windows.net/uploads/missing.pdf"}))
    assert "error" in out and "not in this environment's upload store" in out["error"] and "FileNotFoundError" not in out["error"]
