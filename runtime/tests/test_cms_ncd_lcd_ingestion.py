"""CMS NCD/LCD extraction + chunking tests.

CO-2A.1 replaced the old JSON-API fetch layer with the bulk-download path
(see test_cms_ncd_lcd_bulk.py), so the index-parse / diff / fetcher tests are
gone. The extract_policy + chunk_policy coverage stays — those modules are
unchanged and still consume the NcdDocument / LcdDocument shapes.
"""

from __future__ import annotations

import datetime

import pytest

from app.ingestion.cms_ncd_lcd import (
    LcdDocument,
    NcdDocument,
    PolicySection,
    extract_codes_from_text,
)
from app.ingestion.chunk_policy import chunk_policy
from app.ingestion.extract_policy import extract_policy


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


def test_extract_codes_from_text_numbers_only():
    codes = extract_codes_from_text("Covered: 77067 and HCPCS G0202; dx Z12.31. See CPT 73721.")
    assert "77067" in codes and "73721" in codes
    assert "G0202" in codes
    assert "Z12.31" in codes


@pytest.mark.asyncio
async def test_extract_policy_produces_structured_fields():
    extracted = await extract_policy(_ncd_doc("220.4"))
    assert "77067" in extracted.applicable_codes
    assert extracted.effective_date_start == datetime.date(2002, 1, 1)
    assert extracted.frequency_limits.get("period") == "year"
    assert any("Documentation" in d for d in extracted.documentation_requirements)


@pytest.mark.asyncio
async def test_chunk_policy_one_chunk_per_section():
    doc = _ncd_doc("220.4")
    chunks = chunk_policy(await extract_policy(doc), doc)
    assert len(chunks) == len(doc.sections) == 2


@pytest.mark.asyncio
async def test_chunk_policy_includes_section_heading_inline():
    doc = _ncd_doc("220.4")
    chunks = chunk_policy(await extract_policy(doc), doc)
    for ch, section in zip(chunks, doc.sections):
        assert ch.chunk_text.startswith(section.heading)
        assert section.body in ch.chunk_text


@pytest.mark.asyncio
async def test_chunk_policy_metadata_complete():
    ncd_chunks = chunk_policy(await extract_policy(_ncd_doc("220.4")), _ncd_doc("220.4"))
    c = ncd_chunks[0]
    assert c.payer == "CMS"
    assert c.plan_type == "Medicare"
    assert c.policy_id == "NCD-220.4"
    assert c.jurisdiction == "federal"
    assert "77067" in c.applicable_codes

    lcd_chunks = chunk_policy(await extract_policy(_lcd_doc("L33392")), _lcd_doc("L33392"))
    assert lcd_chunks[0].jurisdiction == "state_CA"
    assert lcd_chunks[0].policy_id == "LCD-L33392"
