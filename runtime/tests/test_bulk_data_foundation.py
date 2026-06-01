"""Phase CO-3A + CO-2A.1 — bulk data foundation tests.

All offline: BlobStorage runs in local-FS mode (tmp dir per test); BulkDownloader
is driven by httpx.MockTransport; parsers run on inline fixtures; estimate_cost
runs against seeded transparency_rates. Live download tests are skipped unless
RUN_LIVE_BULK is set.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import uuid
import zipfile

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.transparency_rates import TransparencyRate, TransparencyRateStaging
from app.ingestion.blob_storage import BlobStorage
from app.ingestion.bulk_download import BulkDownloader
from app.ingestion.ghost_rate_filter import confidence_score, is_likely_ghost
from app.ingestion.parsers import RateRecord
from app.ingestion.parsers.cms_mcd import CmsMcdParser
from app.ingestion.parsers.hospital_mrf import HospitalMrfParser
from app.ingestion.parsers.medicare_pfs import MedicarePfsParser
from app.ingestion.parsers.tic_mrf import TicMrfParser
from app.ingestion.rates_repo import persist_rates
from app.knowledge.cost_estimation import estimate_cost
from app.tools.cost_tools import _cost_estimate_fair_health, _cost_estimate_trilliant


@pytest_asyncio.fixture
async def blob(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "bulk_local_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "azure_storage_connection_string", None)
    return BlobStorage()


async def _stage(blob: BlobStorage, path: str, data: bytes) -> str:
    await blob.write_bytes(path, data)
    return path


def _mock_client(
    content: bytes, *, last_modified="Mon, 01 Jan 2026 00:00:00 GMT", accept_ranges=True
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            h = {"content-length": str(len(content)), "last-modified": last_modified}
            if accept_ranges:
                h["accept-ranges"] = "bytes"
            return httpx.Response(200, headers=h)
        rng = request.headers.get("range")
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            return httpx.Response(206, content=content[start:])
        return httpx.Response(200, content=content)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
# BulkDownloader
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_bulk_downloader_resumes_on_failure(blob):
    content = b"0123456789ABCDEF"
    await blob.write_bytes("f.bin", content[:6])  # a prior partial download
    dl = BulkDownloader(blob, client=_mock_client(content), robots_allow=lambda u: True)
    res = await dl.download("https://x/f.bin", "f.bin", resumable=True)
    assert await blob.read_bytes("f.bin") == content
    assert res.bytes_downloaded_this_run == len(content) - 6  # only the remainder


@pytest.mark.asyncio
async def test_bulk_downloader_respects_robots_txt(blob):
    dl = BulkDownloader(blob, client=_mock_client(b"x"), robots_allow=lambda u: False)
    with pytest.raises(PermissionError):
        await dl.download("https://x/f.bin", "f.bin")


@pytest.mark.asyncio
async def test_bulk_downloader_caches_unchanged_files(blob):
    content = b"hello bulk"
    dl = BulkDownloader(blob, client=_mock_client(content), robots_allow=lambda u: True)
    first = await dl.download("https://x/g.bin", "g.bin")
    assert first.bytes_downloaded_this_run == len(content)
    second = await dl.download("https://x/g.bin", "g.bin")  # same Last-Modified
    assert second.bytes_downloaded_this_run == 0  # served from cache


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #
def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_cms_mcd_parser_extracts_records_from_bulk_zip(blob):
    zb = _zip_bytes(
        {
            "ncd_list.csv": "ncd_id,title,effective_date\n220.4,Mammograms,2002-01-01\n",
            "ncd_text.csv": "ncd_id,text\n220.4,Screening mammography 77067 covered once per year.\n",
            "lcd_list.csv": "lcd_id,title,contractor,state\nL33392,MRI Knee,Noridian,CA\n",
            "lcd_text.csv": "lcd_id,text\nL33392,MRI knee 73721 medically necessary.\n",
        }
    )
    await _stage(blob, "cms.zip", zb)
    recs = [r async for r in CmsMcdParser().parse_file("cms.zip", blob)]
    by_id = {r.policy_id: r for r in recs}
    assert "220.4" in by_id and by_id["220.4"].policy_type == "NCD"
    assert "77067" in by_id["220.4"].sections[0]["applicable_codes"]  # joined text → codes
    lcd = by_id["L33392"]
    assert lcd.policy_type == "LCD" and lcd.mac == "Noridian" and lcd.state == "CA"


@pytest.mark.asyncio
async def test_medicare_pfs_parser_computes_allowable_correctly(blob):
    csv_text = "HCPCS,MODIFIER,DESCRIPTION,NON_FAC_TOTAL\n70553,,MRI brain,17.50\n"
    await _stage(blob, "pfs.csv", csv_text.encode())
    parser = MedicarePfsParser(year=2026, conversion_factor=32.0)
    recs = [r async for r in parser.parse_file("pfs.csv", blob)]
    assert len(recs) == 1
    assert recs[0].code == "70553"
    assert recs[0].rate == round(17.50 * 32.0, 2)  # allowable = total_rvu * CF
    assert recs[0].rate_type == "allowable" and recs[0].source == "medicare_pfs"


@pytest.mark.asyncio
async def test_medicare_pfs_parser_handles_real_pprrvu_shape(blob):
    # Mirrors the real PPRRVU file: preamble rows, a "HCPCS" header with duplicate TOTAL
    # columns (non-fac then fac), a CONV FACTOR column, and a status-only zero-RVU row.
    csv_text = (
        ",,2026 National Physician Fee Schedule RVU File January Release,,,,,\n"
        ",,RELEASED 12/29/2025,,,,,\n"
        "HCPCS,MOD,DESCRIPTION,CODE,WORK RVU,TOTAL,TOTAL,FACTOR\n"
        "00100,,Anesthesia px,J,0.00,0.00,0.00,33.4009\n"
        "70553,,MRI brain,A,5.00,10.00,8.00,33.4009\n"
        "70553,26,MRI brain pro compt,A,3.00,4.00,3.00,33.4009\n"
    )
    await _stage(blob, "pprrvu.csv", csv_text.encode())
    # Pass a deliberately wrong CF to prove the parser reads the file's CONV FACTOR column.
    parser = MedicarePfsParser(year=2026, conversion_factor=99.0)
    recs = [r async for r in parser.parse_file("pprrvu.csv", blob)]
    assert len(recs) == 1  # preamble, zero-RVU (00100), and modifier row all skipped
    assert recs[0].code == "70553"
    assert recs[0].rate == round(10.00 * 33.4009, 2)  # non-fac TOTAL x file CF (not 99.0)
    assert recs[0].raw_metadata["conversion_factor"] == 33.4009


@pytest.mark.asyncio
async def test_hospital_mrf_parser_extracts_negotiated_rates(blob):
    doc = {
        "standard_charge_information": [
            {
                "description": "MRI brain",
                "code_information": [{"code": "70553", "type": "CPT"}],
                "standard_charges": [
                    {
                        "discounted_cash": 800,
                        "payers_information": [
                            {
                                "payer_name": "Aetna",
                                "plan_name": "PPO",
                                "standard_charge_dollar": 620,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    await _stage(blob, "hosp.json", json.dumps(doc).encode())
    recs = [r async for r in HospitalMrfParser("330101").parse_file("hosp.json", blob)]
    neg = [r for r in recs if r.rate_type == "negotiated"]
    assert (
        neg and neg[0].payer == "Aetna" and neg[0].rate == 620.0 and neg[0].hospital_id == "330101"
    )
    assert any(r.rate_type == "cash" and r.rate == 800.0 for r in recs)


@pytest.mark.asyncio
async def test_tic_mrf_parser_streams_jsonl_correctly(blob):
    lines = [
        json.dumps(
            {
                "billing_code_type": "CPT",
                "billing_code": "70553",
                "negotiated_rates": [
                    {
                        "negotiated_prices": [
                            {"negotiated_type": "negotiated", "negotiated_rate": 540.0}
                        ]
                    }
                ],
            }
        ),
        json.dumps(
            {
                "billing_code_type": "CPT",
                "billing_code": "73721",
                "negotiated_rates": [
                    {
                        "negotiated_prices": [
                            {"negotiated_type": "negotiated", "negotiated_rate": 410.0}
                        ]
                    }
                ],
            }
        ),
    ]
    await _stage(blob, "tic.jsonl.gz", gzip.compress(("\n".join(lines)).encode()))
    recs = [r async for r in TicMrfParser("UHC", 2026).parse_file("tic.jsonl.gz", blob)]
    codes = {r.code: r.rate for r in recs}
    assert codes == {"70553": 540.0, "73721": 410.0}
    assert all(r.payer == "UHC" and r.source == "tic_mrf" for r in recs)


# --------------------------------------------------------------------------- #
# Ghost-rate filter (DL-63)
# --------------------------------------------------------------------------- #
def test_ghost_rate_filter_rejects_zero_rates():
    assert is_likely_ghost(0.0, 500.0, 3) is True
    assert is_likely_ghost(-5.0, 500.0, 3) is True


def test_ghost_rate_filter_rejects_extreme_outliers():
    assert is_likely_ghost(10.0, 500.0, 3) is True  # < 30% of baseline
    assert is_likely_ghost(5000.0, 500.0, 3) is True  # > 500% of baseline
    assert is_likely_ghost(450.0, 500.0, 3) is False  # within band


def test_ghost_rate_filter_rejects_single_occurrence():
    assert is_likely_ghost(450.0, 500.0, 1) is True  # only one payer file
    assert is_likely_ghost(450.0, 500.0, 2) is False


def test_confidence_score_weighting():
    # More corroboration → higher; far from baseline → lower; clamped [0,1].
    near = confidence_score(500.0, 500.0, 5, 0)
    far = confidence_score(2000.0, 500.0, 5, 0)
    assert 0.0 <= far < near <= 1.0
    assert confidence_score(500.0, 500.0, 0, 1000) == pytest.approx(0.0, abs=0.01)


# --------------------------------------------------------------------------- #
# estimate_cost (CO-002 Item 3)
# --------------------------------------------------------------------------- #
async def _seed(rows: list[dict]) -> None:
    async with AsyncSessionLocal() as s:
        s.add_all([TransparencyRate(**r) for r in rows])
        await s.commit()


@pytest.mark.asyncio
async def test_estimate_cost_combines_sources_correctly():
    code = f"T{uuid.uuid4().hex[:6]}"
    await _seed(
        [
            {
                "source": "medicare_pfs",
                "code": code,
                "rate": 500,
                "rate_type": "allowable",
                "effective_year": 2026,
                "confidence_score": 1.0,
            },
            {
                "source": "hospital_mrf",
                "code": code,
                "rate": 600,
                "rate_type": "negotiated",
                "effective_year": 2026,
                "confidence_score": 0.8,
                "payer": "Aetna",
            },
            {
                "source": "tic_mrf",
                "code": code,
                "rate": 700,
                "rate_type": "negotiated",
                "effective_year": 2026,
                "confidence_score": 0.9,
                "payer": "UHC",
            },
        ]
    )
    async with AsyncSessionLocal() as s:
        est = await estimate_cost(s, code, location_zip3=None)
    assert "medicare_pfs" in est.sources_used
    assert {"hospital_mrf", "tic_mrf"} & set(est.sources_used)
    assert est.low_estimate <= est.central_estimate <= est.high_estimate


@pytest.mark.asyncio
async def test_estimate_cost_falls_back_to_medicare_baseline_when_no_sources():
    code = f"T{uuid.uuid4().hex[:6]}"
    await _seed(
        [
            {
                "source": "medicare_pfs",
                "code": code,
                "rate": 200,
                "rate_type": "allowable",
                "effective_year": 2026,
                "confidence_score": 1.0,
            }
        ]
    )
    async with AsyncSessionLocal() as s:
        est = await estimate_cost(s, code, location_zip3="021")
    assert est.sources_used == ["medicare_pfs"]
    assert "baseline" in est.confidence_summary.lower()
    assert est.low_estimate < est.central_estimate < est.high_estimate  # ±35% band


@pytest.mark.asyncio
async def test_estimate_cost_returns_confidence_band_never_point_estimate():
    code = f"T{uuid.uuid4().hex[:6]}"
    await _seed(
        [
            {
                "source": "hospital_mrf",
                "code": code,
                "rate": 999,
                "rate_type": "negotiated",
                "effective_year": 2026,
                "confidence_score": 0.8,
                "payer": "X",
            }
        ]
    )
    async with AsyncSessionLocal() as s:
        est = await estimate_cost(s, code, location_zip3=None)
    assert est.central_estimate is not None
    assert est.low_estimate is not None and est.high_estimate is not None  # always a band


# --------------------------------------------------------------------------- #
# Staging (DL-59) + stubs
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_new_source_lands_in_staging_partition_first():
    code = f"S{uuid.uuid4().hex[:6]}"
    rec = RateRecord(
        code=code,
        rate=123.0,
        rate_type="negotiated",
        source="hospital_mrf",
        hospital_id="H1",
        effective_year=2026,
    )
    n = await persist_rates([rec], confidence_fn=lambda r: 0.9, staging=True)
    assert n == 1
    async with AsyncSessionLocal() as s:
        in_staging = (
            (
                await s.execute(
                    select(TransparencyRateStaging).where(TransparencyRateStaging.code == code)
                )
            )
            .scalars()
            .all()
        )
        in_live = (
            (await s.execute(select(TransparencyRate).where(TransparencyRate.code == code)))
            .scalars()
            .all()
        )
    assert len(in_staging) == 1 and len(in_live) == 0  # landed in staging, not live


@pytest.mark.asyncio
async def test_trilliant_stub_returns_not_implemented_with_clear_message():
    with pytest.raises(NotImplementedError) as exc:
        await _cost_estimate_trilliant({"code": "70553"})
    assert "DL-50" in str(exc.value)


@pytest.mark.asyncio
async def test_fair_health_stub_marked_deprecated():
    out = await _cost_estimate_fair_health({"cpt_code": "70553"})
    assert out["deprecated"] is True and "DEPRECATED" in out["error"]


# --------------------------------------------------------------------------- #
# Live integration (skipped without RUN_LIVE_BULK)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not os.getenv("RUN_LIVE_BULK"), reason="requires RUN_LIVE_BULK + network")
@pytest.mark.asyncio
async def test_real_medicare_pfs_download_and_parse():
    from app.ingestion.medicare_pfs import ingest_medicare_pfs

    n = await ingest_medicare_pfs(2026)
    assert n > 0


@pytest.mark.skipif(not os.getenv("RUN_LIVE_BULK"), reason="requires RUN_LIVE_BULK + network")
@pytest.mark.asyncio
async def test_real_hospital_mrf_download_for_one_top_100_hospital():
    from app.crons._cron_util import load_top_100_hospitals
    from app.ingestion.hospital_mrf import ingest_hospital_mrf

    h = load_top_100_hospitals()[0]
    await ingest_hospital_mrf(h["hospital_id"], h["mrf_url"], hospital_zip3=h.get("zip3"))


@pytest.mark.skipif(not os.getenv("RUN_LIVE_BULK"), reason="requires RUN_LIVE_BULK + network")
@pytest.mark.asyncio
async def test_real_tic_mrf_streaming_for_one_payer():
    from app.crons._cron_util import load_tier1_payer_indices
    from app.ingestion.tic_mrf import ingest_tic_payer

    p = load_tier1_payer_indices()[0]
    await ingest_tic_payer(p["payer"], year=2026, index_url=p["index_url"], max_files=1)


@pytest.mark.asyncio
async def test_pfs_zip_url_discovery_two_hop():
    """CO-3A real-source fix: PFS index -> RVU26A item page -> the actual zip URL.

    Exact anchor-text match must pick RVU26A (not RVU26AR or RVU25A).
    """
    from app.ingestion.medicare_pfs import discover_pfs_zip_url

    index_html = (
        '<a href="/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu26ar">'
        "RVU26AR</a>"
        '<a href="/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu25a">'
        "RVU25A</a>"
        '<a href="/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu26a">'
        "RVU26A</a>"
    )
    item_html = '<a href="/files/zip/rvu26a-updated-12-29-2025.zip">Download ZIP</a>'

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pfs-relative-value-files"):
            return httpx.Response(200, text=index_html)
        if path.endswith("/rvu26a"):
            return httpx.Response(200, text=item_html)
        return httpx.Response(404, text="not found")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        url = await discover_pfs_zip_url(2026, client=client)
    finally:
        await client.aclose()
    assert url == "https://www.cms.gov/files/zip/rvu26a-updated-12-29-2025.zip"
