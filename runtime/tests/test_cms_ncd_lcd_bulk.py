"""Phase CO-2A.1 / CO-3A — CMS NCD/LCD bulk-download ingestion tests.

The bulk parser + the end-to-end ingest_from_bulk path, against a fixture that mirrors
the real 3-level nested export (download mocked by a pre-staged ZIP; stub embeddings +
in-memory Qdrant).
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


def _zip(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buf.getvalue()


# Real denormalized schemas (NCD one table; LCD main table + HCPCS join table).
_NCD_TRKG = (
    "NCD_id,NCD_mnl_sect,NCD_mnl_sect_title,NCD_efctv_dt,itm_srvc_desc,indctn_lmtn\n"
    '1,"220.4","Screening Mammography","2002-01-01 00:00:00",'
    '"Screening mammography","77067 covered once per year."\n'
    '2,"220.1","Computed Tomography","2000-01-01 00:00:00","CT scans","70450 medically necessary."\n'
)
_LCD = (
    "lcd_id,title,rev_eff_date,indication,coding_guidelines\n"
    '"33392","MRI of the Knee","2020-07-01 00:00:00",'
    '"MRI knee medically necessary after conservative therapy.","See covered codes."\n'
)
_LCD_HCPC = 'lcd_id,hcpc_code_id\n"33392","73721"\n'


def _nested_all_data() -> bytes:
    """Build all_data.zip with the real 3-level nesting (zip -> *_csv.zip -> CSVs)."""
    ncd = _zip({"ncd_csv.zip": _zip({"ncd_trkg.csv": _NCD_TRKG}), "readme_first.txt": "x"})
    lcd_csv = _zip({"lcd.csv": _LCD, "lcd_x_hcpc_code.csv": _LCD_HCPC})
    lcd = _zip({"current_lcd_csv.zip": lcd_csv})
    return _zip({"ncd.zip": ncd, "current_lcd.zip": lcd})


@pytest_asyncio.fixture
async def blob(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "bulk_local_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "azure_storage_connection_string", None)
    b = BlobStorage()
    await b.write_bytes("cms-mcd/all_data.zip", _nested_all_data())
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
async def test_cms_mcd_parser_extracts_records_from_nested_zip(blob):
    recs = [r async for r in CmsMcdParser().parse_file("cms-mcd/all_data.zip", blob)]
    # NCDs keyed by manual section; LCD keyed L{lcd_id}.
    assert {r.policy_id for r in recs} >= {"220.4", "220.1", "L33392"}


@pytest.mark.asyncio
async def test_cms_mcd_parser_codes_from_ncd_text_and_lcd_join(blob):
    recs = {
        r.policy_id: r
        for r in [x async for x in CmsMcdParser().parse_file("cms-mcd/all_data.zip", blob)]
    }
    # NCD codes extracted from the denormalized body text.
    assert "77067" in recs["220.4"].sections[0]["applicable_codes"]
    # LCD codes come from the lcd_x_hcpc_code join table, not regex over text.
    assert "73721" in recs["L33392"].sections[0]["applicable_codes"]


@pytest.mark.asyncio
async def test_cms_mcd_parser_type_and_iso_date(blob):
    recs = {
        r.policy_id: r
        for r in [x async for x in CmsMcdParser().parse_file("cms-mcd/all_data.zip", blob)]
    }
    lcd = recs["L33392"]
    assert lcd.policy_type == "LCD"
    assert lcd.effective_date == "2020-07-01"  # "...00:00:00" trimmed to ISO date
    ncd = recs["220.4"]
    assert ncd.policy_type == "NCD" and ncd.effective_date == "2002-01-01"


@pytest.mark.asyncio
async def test_run_sample_ingestion_with_bulk_download(blob, memory_qdrant):
    # ingest_from_bulk with a pre-staged blob_path = no network; stub embeddings.
    report = await cms_ncd_lcd.ingest_from_bulk(blob=blob, blob_path="cms-mcd/all_data.zip")
    assert report["attempted"] == 3  # 2 NCD + 1 LCD
    assert report["failed"] == 0
    assert report["chunks_upserted"] >= 3

    hits = await search("payer_policies", "screening mammography", effective_date="2026-05-30")
    assert hits
    assert all(h.payload.get("payer") == "CMS" for h in hits)
