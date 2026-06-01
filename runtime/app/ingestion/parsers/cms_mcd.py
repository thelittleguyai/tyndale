"""CMS Medicare Coverage Database bulk parser (Phase CO-2A.1).

VERIFIED 2026-05-30: the real bulk source is
https://downloads.cms.gov/medicare-coverage-database/downloads/exports/*.zip
(all_data.zip, current_lcd.zip, all_lcd.zip, current_article.zip, …) — NOT the
JSON report API the original CO-2A assumed (which 302-redirects to HTML).

The ZIPs contain CSV exports. Exact CSV filenames + columns are not pinned here
(they vary across CMS export bundles), so this parser classifies CSVs by content:
a "list" CSV has an id + title column; a "text" CSV has an id + a long-text body;
they join on the policy id. Column lookup is alias-based + case-insensitive, so
minor header differences are tolerated. ADAPT the alias sets if a real export
differs (the prompt's verify-at-implementation-time license).
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import AsyncIterator

import structlog

from app.ingestion.cms_ncd_lcd import extract_codes_from_text
from app.ingestion.parsers import BulkSourceParser, ParsedRecord, PolicyRecord

log = structlog.get_logger(__name__)

_ID_ALIASES = ("ncd_id", "lcd_id", "document_id", "doc_id", "id", "policy_id")
_TITLE_ALIASES = ("title", "ncd_title", "lcd_title", "document_title", "name")
_EFF_ALIASES = ("effective_date", "eff_date", "effectivedate", "rev_eff_date")
_MOD_ALIASES = ("last_updated", "revision_date", "last_modified", "lastmodified")
_MAC_ALIASES = ("contractor", "contractor_name", "mac", "contractor_bus_name")
_STATE_ALIASES = ("state", "geo_state", "jurisdiction_state")
_TEXT_ALIASES = ("text", "body", "description", "indication", "full_text", "policy_text", "content")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _rows(raw: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    return [{(k or "").strip().lower(): (v or "") for k, v in row.items()} for row in reader]


def _pick(row: dict, aliases: tuple[str, ...]) -> str | None:
    for a in aliases:
        if row.get(a):
            return row[a].strip()
    return None


def _has(rows: list[dict], aliases: tuple[str, ...]) -> bool:
    return bool(rows) and any(_pick(rows[0], aliases) is not None for _ in (0,))


class CmsMcdParser(BulkSourceParser):
    source_name = "cms_mcd"

    async def parse_file(self, blob_path: str, blob_storage) -> AsyncIterator[ParsedRecord]:
        path = await blob_storage.materialize_local(blob_path)
        list_csvs: dict[str, list[dict]] = {}
        text_maps: list[dict[str, str]] = []

        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                rows = _rows(zf.read(name))
                if not rows:
                    continue
                has_id = _pick(rows[0], _ID_ALIASES) is not None
                has_title = _pick(rows[0], _TITLE_ALIASES) is not None
                has_text = _pick(rows[0], _TEXT_ALIASES) is not None
                if has_id and has_title:
                    list_csvs[name] = rows
                elif has_id and has_text:
                    text_maps.append(
                        {
                            _pick(r, _ID_ALIASES): _pick(r, _TEXT_ALIASES) or ""
                            for r in rows
                            if _pick(r, _ID_ALIASES)
                        }
                    )

        for name, rows in list_csvs.items():
            ptype = "LCD" if "lcd" in name.lower() else "NCD"
            for row in rows:
                pid = _pick(row, _ID_ALIASES)
                if not pid:
                    continue
                title = _pick(row, _TITLE_ALIASES) or ""
                body = next((m[pid] for m in text_maps if pid in m), "") or title
                yield PolicyRecord(
                    policy_id=pid,
                    policy_type=ptype,
                    title=title,
                    effective_date=_pick(row, _EFF_ALIASES),
                    last_modified=_pick(row, _MOD_ALIASES),
                    mac=_pick(row, _MAC_ALIASES) if ptype == "LCD" else None,
                    state=_pick(row, _STATE_ALIASES) if ptype == "LCD" else None,
                    sections=[
                        {
                            "heading": title or "Coverage",
                            "body": body,
                            "applicable_codes": extract_codes_from_text(f"{title} {body}"),
                            "section_number": "1",
                        }
                    ],
                )
