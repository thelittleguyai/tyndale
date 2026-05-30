"""Phase CO-2A — CMS NCD/LCD ingestion tests.

All offline: index/document parsing runs on inline fixtures (no network), extraction
uses the deterministic stub (no ANTHROPIC_API_KEY), and the end-to-end sample run
uses injected fixture fetchers + in-memory Qdrant + stub embeddings (no Docker, no
VOYAGE_API_KEY). One live integration test is skipped unless VOYAGE_API_KEY is set.
"""

from __future__ import annotations

import datetime
import os

import pytest
import pytest_asyncio

from app.ingestion.cms_ncd_lcd import (
    LcdDocument,
    LcdSummary,
    NcdDocument,
    NcdSummary,
    PolicySection,
    diff_since,
    extract_codes_from_text,
    parse_lcd_index,
    parse_ncd_index,
)
from app.ingestion.chunk_policy import chunk_policy
from app.ingestion.extract_policy import extract_policy
from app.ingestion.run_ncd_lcd_ingestion import run_sample_ingestion
from app.knowledge.search import search

# --------------------------------------------------------------------------- #
# Fixtures (inline — modeled on the MCD report JSON shape)
# --------------------------------------------------------------------------- #
_NCD_INDEX_JSON = {
    "data": [
        {
            "ncd_id": "220.4",
            "title": "Mammograms",
            "effective_date": "2002-01-01",
            "last_modified": "2020-06-01",
            "document_url": "https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?ncdid=220.4",
        },
        {
            "ncd_id": "220.1",
            "title": "Computed Tomography",
            "effective_date": "2000-01-01",
            "last_modified": "2019-02-01",
        },
    ]
}

_LCD_INDEX_JSON = {
    "results": [
        {
            "lcd_id": "L33392",
            "title": "MRI and CT of the Knee",
            "contractor": "Noridian Healthcare Solutions",
            "state": "CA",
            "effective_date": "2019-01-01",
            "last_modified": "2023-03-01",
        },
        {
            "lcd_id": "L34567",
            "title": "Something in New York",
            "contractor": "NGS",
            "state": "NY",
            "effective_date": "2018-01-01",
            "last_modified": "2022-01-01",
        },
    ]
}


def _ncd_doc(ncd_id: str) -> NcdDocument:
    return NcdDocument(
        ncd_id=ncd_id,
        title=f"NCD {ncd_id} Screening Mammography",
        full_text="Screening mammography 77067 is covered once per year. Prior authorization not required.",
        sections=[
            PolicySection(
                heading="Indications and Limitations of Coverage",
                body="Screening mammography (77067) is covered once per year per beneficiary.",
                applicable_codes=["77067"],
                section_number="1",
            ),
            PolicySection(
                heading="Documentation Requirements",
                body="The medical record must support the screening interval.",
                applicable_codes=[],
                section_number="2",
            ),
        ],
        effective_date="2002-01-01",
        parent_part="Part 2",
        parent_subpart="220",
    )


def _lcd_doc(lcd_id: str) -> LcdDocument:
    return LcdDocument(
        lcd_id=lcd_id,
        title=f"LCD {lcd_id} MRI of the Knee",
        mac="Noridian Healthcare Solutions",
        state="CA",
        full_text="MRI of the knee 73721 is medically necessary after conservative therapy.",
        sections=[
            PolicySection(
                heading="Coverage Indications",
                body="MRI knee (73721) medically necessary after a trial of conservative therapy.",
                applicable_codes=["73721"],
                section_number="1",
            )
        ],
        effective_date="2019-01-01",
    )


async def _fake_ncd_index() -> list[NcdSummary]:
    return [
        NcdSummary(
            ncd_id=f"220.{i}",
            title=f"NCD 220.{i} Screening Mammography",
            effective_date="2002-01-01",
            last_modified="2020-06-01",
            document_url="https://example/ncd",
        )
        for i in range(1, 7)
    ]


async def _fake_lcd_index(state: str | None = None) -> list[LcdSummary]:
    return [
        LcdSummary(
            lcd_id=f"L3339{i}",
            title=f"LCD L3339{i} MRI of the Knee",
            mac="Noridian Healthcare Solutions",
            state=state or "CA",
            effective_date="2019-01-01",
            last_modified="2023-03-01",
            document_url="https://example/lcd",
        )
        for i in range(1, 7)
    ]


async def _fake_ncd_document(ncd_id: str) -> NcdDocument:
    return _ncd_doc(ncd_id)


async def _fake_lcd_document(lcd_id: str) -> LcdDocument:
    return _lcd_doc(lcd_id)


@pytest_asyncio.fixture
async def memory_qdrant(monkeypatch):
    """Force the shared Qdrant client into in-memory mode + stub embeddings."""
    import app.knowledge.client as kc
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "qdrant_url", ":memory:")
    monkeypatch.setattr(get_settings(), "voyage_api_key", None)  # stub vectors
    kc._client = None
    yield
    kc._client = None  # next user re-resolves a fresh client


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def test_fetch_ncd_index_parses_correctly():
    summaries = parse_ncd_index(_NCD_INDEX_JSON)
    assert len(summaries) == 2
    s = summaries[0]
    assert s.ncd_id == "220.4"
    assert s.title == "Mammograms"
    assert s.effective_date == "2002-01-01"
    assert s.last_modified == "2020-06-01"
    assert s.document_url.endswith("ncdid=220.4")
    # missing document_url falls back to a constructed MCD url
    assert summaries[1].document_url.endswith("ncdid=220.1")


def test_fetch_lcd_index_parses_with_mac_metadata():
    summaries = parse_lcd_index(_LCD_INDEX_JSON)
    assert len(summaries) == 2
    ca = next(s for s in summaries if s.lcd_id == "L33392")
    assert ca.mac == "Noridian Healthcare Solutions"
    assert ca.state == "CA"
    assert ca.effective_date == "2019-01-01"
    # state filter narrows the index
    only_ca = parse_lcd_index(_LCD_INDEX_JSON, state="CA")
    assert [s.lcd_id for s in only_ca] == ["L33392"]


def test_extract_codes_from_text_numbers_only():
    codes = extract_codes_from_text("Covered: 77067 and HCPCS G0202; dx Z12.31. See CPT 73721.")
    assert "77067" in codes and "73721" in codes
    assert "G0202" in codes
    assert "Z12.31" in codes


# --------------------------------------------------------------------------- #
# Extraction (stub path — no key)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_extract_policy_produces_structured_fields():
    extracted = await extract_policy(_ncd_doc("220.4"))
    assert "77067" in extracted.applicable_codes  # codes pulled from sections + full_text
    assert extracted.effective_date_start == datetime.date(2002, 1, 1)
    assert extracted.frequency_limits.get("period") == "year"  # "once per year"
    assert any("Documentation" in d for d in extracted.documentation_requirements)
    # deterministic + serializable
    assert extracted.to_dict()["effective_date_start"] == "2002-01-01"


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_chunk_policy_one_chunk_per_section():
    doc = _ncd_doc("220.4")
    extracted = await extract_policy(doc)
    chunks = chunk_policy(extracted, doc)
    assert len(chunks) == len(doc.sections) == 2


@pytest.mark.asyncio
async def test_chunk_policy_includes_section_heading_inline():
    doc = _ncd_doc("220.4")
    chunks = chunk_policy(await extract_policy(doc), doc)
    for ch, section in zip(chunks, doc.sections):
        assert ch.chunk_text.startswith(section.heading)  # heading inline at top (§8)
        assert section.body in ch.chunk_text


@pytest.mark.asyncio
async def test_chunk_policy_metadata_complete():
    ncd_chunks = chunk_policy(await extract_policy(_ncd_doc("220.4")), _ncd_doc("220.4"))
    c = ncd_chunks[0]
    assert c.payer == "CMS"
    assert c.plan_type == "Medicare"
    assert c.policy_id == "NCD-220.4"
    assert c.jurisdiction == "federal"
    assert c.effective_date_start == "2002-01-01"
    assert c.effective_date_end is None
    assert c.last_verified_date  # ingestion timestamp present
    assert c.parent_title and c.parent_part == "Part 2"
    assert "77067" in c.applicable_codes

    lcd_chunks = chunk_policy(await extract_policy(_lcd_doc("L33392")), _lcd_doc("L33392"))
    assert lcd_chunks[0].jurisdiction == "state_CA"
    assert lcd_chunks[0].policy_id == "LCD-L33392"


# --------------------------------------------------------------------------- #
# Diff
# --------------------------------------------------------------------------- #
def test_diff_since_returns_only_changed():
    index = [
        NcdSummary("220.4", "Mammograms", "2002-01-01", "2020-06-01", "u"),  # changed (after last)
        NcdSummary("220.1", "CT", "2000-01-01", "2019-02-01", "u"),  # unchanged (before last)
        NcdSummary("220.9", "New", "2024-01-01", "2024-01-01", "u"),  # brand new (not indexed)
    ]
    last = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    last_indexed = {"220.4": last, "220.1": last}  # 220.9 absent => new
    changed = diff_since(last_indexed, index)
    ids = {c.policy_id for c in changed}
    assert ids == {"220.4", "220.9"}  # 220.1 (older than last_indexed) excluded


# --------------------------------------------------------------------------- #
# End-to-end sample (injected fetchers + in-memory Qdrant + stub embeddings)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_run_sample_ingestion_end_to_end(memory_qdrant):
    report = await run_sample_ingestion(
        fetch_ncd_index=_fake_ncd_index,
        fetch_lcd_index=_fake_lcd_index,
        fetch_ncd_document=_fake_ncd_document,
        fetch_lcd_document=_fake_lcd_document,
    )
    assert report.attempted == 10  # 5 NCDs + 5 CA LCDs
    assert report.failed == 0
    assert report.chunks_upserted >= 10  # 5*2 NCD sections + 5*1 LCD section = 15

    hits = await search(
        "payer_policies",
        "screening mammography Medicare frequency",
        effective_date="2026-05-30",
    )
    assert hits, "effective-date-filtered search returned no CMS hits"
    assert all(h.payload.get("payer") == "CMS" for h in hits)  # payer='CMS' (confirmation c)
    assert any(str(h.payload.get("policy_id", "")).startswith("NCD-") for h in hits)
    # section heading inline at top of chunk_text (developer-spec §8)
    assert any("\n\n" in str(h.payload.get("chunk_text", "")) for h in hits)


@pytest.mark.asyncio
async def test_sample_ingestion_idempotent(memory_qdrant):
    """Re-ingesting the same version upserts in place — no duplicate points."""
    kw = dict(
        fetch_ncd_index=_fake_ncd_index,
        fetch_lcd_index=_fake_lcd_index,
        fetch_ncd_document=_fake_ncd_document,
        fetch_lcd_document=_fake_lcd_document,
    )
    await run_sample_ingestion(**kw)
    first = await search("payer_policies", "mammography", effective_date="2026-05-30")
    await run_sample_ingestion(**kw)
    second = await search("payer_policies", "mammography", effective_date="2026-05-30")
    assert len(second) == len(first)  # stable point ids => idempotent


# --------------------------------------------------------------------------- #
# Live integration (skipped without a real key)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not os.getenv("VOYAGE_API_KEY"), reason="requires VOYAGE_API_KEY + reachable Qdrant"
)
@pytest.mark.asyncio
async def test_real_voyage_embeddings_and_qdrant_upsert():
    from app.ingestion.run_ncd_lcd_ingestion import ingest_document

    n = await ingest_document(_ncd_doc("220.4"))
    assert n >= 1
    hits = await search(
        "payer_policies", "screening mammography frequency", effective_date="2026-05-30"
    )
    assert any(str(h.payload.get("policy_id", "")) == "NCD-220.4" for h in hits)
