"""Phase CO-2A.1 — CMS NCD/LCD bulk-download ingestion tests.

The bulk parser + the end-to-end ingest_from_bulk path (download mocked by a
pre-staged fixture ZIP; stub embeddings + in-memory Qdrant).
"""

from __future__ import annotations

import io
import zipfile

import pytest
import pytest_asyncio

from app.config import get_settings
from app.ingestion import cms_ncd_lcd
from app.ingestion.blob_storage import BlobStorage
from app.ingestion.parsers.cms_mcd import CmsMcdParser
from app.knowledge.search import search


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buf.getvalue()


_FIXTURE = {
    "ncd_list.csv": "ncd_id,title,effective_date\n220.4,Screening Mammography,2002-01-01\n220.1,CT Scans,2000-01-01\n",
    "ncd_text.csv": "ncd_id,text\n220.4,Screening mammography 77067 covered once per year.\n220.1,CT 70450 medically necessary.\n",
    "lcd_list.csv": "lcd_id,title,contractor,state\nL33392,MRI of the Knee,Noridian Healthcare,CA\n",
    "lcd_text.csv": "lcd_id,text\nL33392,MRI knee 73721 medically necessary after conservative therapy.\n",
}


@pytest_asyncio.fixture
async def blob(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "bulk_local_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "azure_storage_connection_string", None)
    b = BlobStorage()
    await b.write_bytes("cms-mcd/all_data.zip", _zip(_FIXTURE))
    return b


@pytest_asyncio.fixture
async def memory_qdrant(monkeypatch):
    import app.knowledge.client as kc

    monkeypatch.setattr(get_settings(), "qdrant_url", ":memory:")
    monkeypatch.setattr(get_settings(), "voyage_api_key", None)
    kc._client = None
    yield
    kc._client = None


@pytest.mark.asyncio
async def test_cms_mcd_parser_extracts_records_from_bulk_zip(blob):
    recs = [r async for r in CmsMcdParser().parse_file("cms-mcd/all_data.zip", blob)]
    assert {r.policy_id for r in recs} >= {"220.4", "220.1", "L33392"}


@pytest.mark.asyncio
async def test_cms_mcd_parser_joins_list_and_text_csvs(blob):
    recs = {
        r.policy_id: r
        for r in [x async for x in CmsMcdParser().parse_file("cms-mcd/all_data.zip", blob)]
    }
    # body came from the *_text.csv, joined by id
    assert "77067" in recs["220.4"].sections[0]["body"]
    assert "73721" in recs["L33392"].sections[0]["body"]


@pytest.mark.asyncio
async def test_cms_mcd_parser_handles_lcd_with_mac_metadata(blob):
    recs = {
        r.policy_id: r
        for r in [x async for x in CmsMcdParser().parse_file("cms-mcd/all_data.zip", blob)]
    }
    lcd = recs["L33392"]
    assert lcd.policy_type == "LCD" and lcd.mac == "Noridian Healthcare" and lcd.state == "CA"


@pytest.mark.asyncio
async def test_run_sample_ingestion_with_bulk_download(blob, memory_qdrant):
    # ingest_from_bulk with a pre-staged blob_path = no network; stub embeddings.
    report = await cms_ncd_lcd.ingest_from_bulk(blob=blob, blob_path="cms-mcd/all_data.zip")
    assert report["attempted"] == 3
    assert report["failed"] == 0
    assert report["chunks_upserted"] >= 3

    hits = await search("payer_policies", "screening mammography", effective_date="2026-05-30")
    assert hits
    assert all(h.payload.get("payer") == "CMS" for h in hits)
