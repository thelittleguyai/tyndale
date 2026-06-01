"""CMS Medicare Coverage Database — document shapes + bulk ingestion (CO-2A.1).

VERIFIED 2026-05-30: the original CO-2A JSON report endpoints don't exist (they
302-redirect to HTML). The real source is CMS's downloadable bulk databases:
https://downloads.cms.gov/medicare-coverage-database/downloads/exports/*.zip
(all_data.zip, current_lcd.zip, all_lcd.zip, …). This module now ingests from
that bulk path; the chunk → extract → embed → upsert pipeline is unchanged.

Kept here (imported by chunk_policy / extract_policy / the CmsMcdParser): the
NcdDocument / LcdDocument / PolicySection shapes + extract_codes_from_text. The
old fetch_* / parse_*index / HTML-document network layer is removed.

DL-54: code NUMBERS are stored as facts; AMA CPT descriptors are never synthesized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# Real CMS MCD bulk exports (verified live). all_data.zip carries NCDs + LCDs.
CMS_BULK_BASE = "https://downloads.cms.gov/medicare-coverage-database/downloads/exports"
CMS_BULK_ALL_DATA_URL = f"{CMS_BULK_BASE}/all_data.zip"
CMS_BULK_LCD_URL = f"{CMS_BULK_BASE}/current_lcd.zip"

# Code-extraction regexes (facts on the public-domain source; DL-54: numbers only).
_CPT_RE = re.compile(r"\b\d{5}\b")
_HCPCS_RE = re.compile(r"\b[A-V]\d{4}\b")
_ICD10_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,4})?\b")


# --------------------------------------------------------------------------- #
# Document shapes (consumed by extract_policy + chunk_policy)
# --------------------------------------------------------------------------- #
@dataclass
class PolicySection:
    heading: str
    body: str
    applicable_codes: list[str] = field(default_factory=list)
    section_number: str | None = None


@dataclass
class NcdDocument:
    ncd_id: str
    title: str
    full_text: str
    sections: list[PolicySection]
    effective_date: str | None = None
    last_modified: str | None = None
    parent_part: str | None = None
    parent_subpart: str | None = None

    @property
    def policy_id(self) -> str:
        return f"NCD-{self.ncd_id}"


@dataclass
class LcdDocument:
    lcd_id: str
    title: str
    mac: str | None
    state: str | None
    full_text: str
    sections: list[PolicySection]
    effective_date: str | None = None
    last_modified: str | None = None
    parent_part: str | None = None
    parent_subpart: str | None = None

    @property
    def policy_id(self) -> str:
        return f"LCD-{self.lcd_id}"


def extract_codes_from_text(text: str) -> list[str]:
    """CPT/HCPCS/ICD-10 code numbers in ``text`` (deduped, ordered). Facts only."""
    if not text:
        return []
    seen: dict[str, None] = {}
    for rx in (_HCPCS_RE, _ICD10_RE, _CPT_RE):
        for m in rx.finditer(text):
            seen.setdefault(m.group(0), None)
    return list(seen.keys())


def _to_document(rec) -> NcdDocument | LcdDocument:
    """Convert a parser PolicyRecord into the pipeline's document shape."""
    sections = [
        PolicySection(
            heading=s.get("heading", "Coverage"),
            body=s.get("body", ""),
            applicable_codes=list(s.get("applicable_codes") or []),
            section_number=s.get("section_number"),
        )
        for s in rec.sections
    ]
    full_text = " ".join(s.body for s in sections)
    if rec.policy_type == "LCD":
        return LcdDocument(
            lcd_id=rec.policy_id,
            title=rec.title,
            mac=rec.mac,
            state=rec.state,
            full_text=full_text,
            sections=sections,
            effective_date=rec.effective_date,
            last_modified=rec.last_modified,
        )
    return NcdDocument(
        ncd_id=rec.policy_id,
        title=rec.title,
        full_text=full_text,
        sections=sections,
        effective_date=rec.effective_date,
        last_modified=rec.last_modified,
    )


# --------------------------------------------------------------------------- #
# Bulk ingestion (CO-2A.1) — download → parse → chunk → embed → upsert
# --------------------------------------------------------------------------- #
async def ingest_from_bulk(
    *,
    source_url: str = CMS_BULK_ALL_DATA_URL,
    blob: Any | None = None,
    downloader: Any | None = None,
    blob_path: str | None = None,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    """Download the CMS bulk ZIP (idempotent via the downloader cache), stream
    policies out of it, and run the existing chunk/embed/upsert pipeline.

    Tests inject a pre-staged ``blob_path`` (a fixture ZIP) + a stub ``blob`` to
    skip the network. Lazy imports avoid the cms_mcd ↔ cms_ncd_lcd circular."""
    from app.ingestion.blob_storage import BlobStorage
    from app.ingestion.bulk_download import BulkDownloader
    from app.ingestion.chunk_policy import chunk_policy, embed_and_upsert
    from app.ingestion.extract_policy import extract_policy
    from app.ingestion.parsers.cms_mcd import CmsMcdParser

    blob = blob or BlobStorage()
    if blob_path is None:
        dl = downloader or BulkDownloader(blob)
        res = await dl.download(source_url, "cms-mcd/all_data.zip")
        blob_path = res.blob_path

    results: list[dict] = []
    chunks_total = 0
    async for rec in CmsMcdParser().parse_file(blob_path, blob):
        if sample_limit is not None and len(results) >= sample_limit:
            break
        try:
            doc = _to_document(rec)
            extracted = await extract_policy(doc)
            chunks = chunk_policy(extracted, doc)
            n = await embed_and_upsert(chunks)
            results.append({"policy_id": doc.policy_id, "ok": True, "chunks": n})
            chunks_total += n
        except Exception as e:  # noqa: BLE001 — per-policy isolation
            log.warning("cms_bulk.policy_failed", policy_id=rec.policy_id, error=str(e))
            results.append(
                {"policy_id": f"{rec.policy_type}-{rec.policy_id}", "ok": False, "error": str(e)}
            )

    return {
        "attempted": len(results),
        "succeeded": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "chunks_upserted": chunks_total,
        "results": results,
    }
