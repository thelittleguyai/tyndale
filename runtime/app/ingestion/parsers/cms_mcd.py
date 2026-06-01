"""CMS Medicare Coverage Database bulk parser (Phase CO-2A.1 / CO-3A real-source fix).

VERIFIED 2026-06-01 against the live all_data.zip: the export is a THREE-LEVEL nested
zip. all_data.zip holds per-collection zips (ncd.zip, current_lcd.zip, all_lcd.zip,
current_article.zip, all_article.zip); each holds a *_csv.zip with the actual CSVs (plus
a .mdb Access copy + data-dictionary PDF we ignore). This parser recurses into ncd.zip +
current_lcd.zip (skipping retired 'all_*' bundles and Articles) and maps the real
denormalized schemas:

  NCD: ncd_trkg.csv — NCD_id / NCD_mnl_sect (the citable section, e.g. 220.4) /
       NCD_mnl_sect_title / NCD_efctv_dt / itm_srvc_desc + indctn_lmtn (body). One row/NCD.
  LCD: lcd.csv — lcd_id / title / rev_eff_date / indication + coding_guidelines (body),
       joined to lcd_x_hcpc_code.csv (lcd_id -> hcpc_code_id) for the authoritative
       covered-HCPCS list. LCD MAC/state live in the contractor join tables (refinement).
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import AsyncIterator, Iterator

import structlog

from app.ingestion.cms_ncd_lcd import extract_codes_from_text
from app.ingestion.parsers import BulkSourceParser, ParsedRecord, PolicyRecord

log = structlog.get_logger(__name__)

# LCD body columns (indication / source_info) routinely exceed the 128 KB csv default.
csv.field_size_limit(16 * 1024 * 1024)

_NCD_FILE = "ncd_trkg.csv"
_LCD_FILE = "lcd.csv"
_LCD_HCPC_FILE = "lcd_x_hcpc_code.csv"

_NCD_BODY = ("itm_srvc_desc", "indctn_lmtn", "othr_txt", "xref_txt")
_LCD_BODY = (
    "indication",
    "diagnoses_support",
    "coding_guidelines",
    "doc_reqs",
    "util_guide",
    "source_info",
)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _collect_csvs(path: str) -> dict[str, bytes]:
    """Recurse the nested export -> {lowercased basename: csv bytes}.

    Descends nested zips but skips retired 'all_*' bundles and Article bundles, so the
    corpus is current NCDs + current LCDs.
    """
    out: dict[str, bytes] = {}

    def walk(zf: zipfile.ZipFile) -> None:
        for name in zf.namelist():
            low = name.lower()
            base = low.rsplit("/", 1)[-1]
            if low.endswith(".csv"):
                out.setdefault(base, zf.read(name))
            elif low.endswith(".zip"):
                if base.startswith("all_") or "article" in base:
                    continue
                with zipfile.ZipFile(io.BytesIO(zf.read(name))) as inner:
                    walk(inner)

    with zipfile.ZipFile(path) as top:
        walk(top)
    return out


def _iter_rows(raw: bytes | None) -> Iterator[dict]:
    if not raw:
        return
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    for row in reader:
        yield {(k or "").strip().lower(): (v or "") for k, v in row.items()}


def _pick(row: dict, aliases: tuple[str, ...]) -> str | None:
    for a in aliases:
        v = row.get(a)
        if v and v.strip():
            return v.strip()
    return None


def _join(row: dict, cols: tuple[str, ...]) -> str:
    parts = [row[c].strip() for c in cols if row.get(c) and row[c].strip()]
    return "\n\n".join(parts)


def _date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    # CMS dates look like "2024-05-27 00:00:00" — keep the ISO date part.
    return s[:10] if len(s) >= 10 and s[4] == "-" and s[7] == "-" else s


def _code_index(raw: bytes | None) -> dict[str, set[str]]:
    """lcd_id -> {covered HCPCS codes} from lcd_x_hcpc_code.csv."""
    idx: dict[str, set[str]] = {}
    for row in _iter_rows(raw):
        lcd_id = _pick(row, ("lcd_id",))
        code = _pick(row, ("hcpc_code_id", "hcpc_code", "code"))
        if lcd_id and code:
            idx.setdefault(lcd_id, set()).add(code)
    return idx


class CmsMcdParser(BulkSourceParser):
    source_name = "cms_mcd"

    async def parse_file(self, blob_path: str, blob_storage) -> AsyncIterator[ParsedRecord]:
        path = await blob_storage.materialize_local(blob_path)
        csvs = _collect_csvs(path)
        hcpc_by_lcd = _code_index(csvs.get(_LCD_HCPC_FILE))

        # --- NCDs: ncd_trkg.csv is denormalized (one row per NCD) ---
        for row in _iter_rows(csvs.get(_NCD_FILE)):
            section = _pick(row, ("ncd_mnl_sect",))
            pid = section or _pick(row, ("ncd_id",))
            if not pid:
                continue
            title = _pick(row, ("ncd_mnl_sect_title",)) or ""
            body = _join(row, _NCD_BODY) or title
            yield self._policy(
                "NCD",
                pid,
                title,
                _date(_pick(row, ("ncd_efctv_dt",))),
                _date(_pick(row, ("last_updt_tmstmp", "creatd_tmstmp"))),
                body,
                section or "1",
                extract_codes_from_text(f"{title}\n{body}"),
            )

        # --- LCDs: lcd.csv joined to lcd_x_hcpc_code.csv for the covered-HCPCS list ---
        for row in _iter_rows(csvs.get(_LCD_FILE)):
            lcd_id = _pick(row, ("lcd_id",))
            if not lcd_id:
                continue
            title = _pick(row, ("title",)) or ""
            body = _join(row, _LCD_BODY) or title
            codes = sorted(hcpc_by_lcd.get(lcd_id, set())) or extract_codes_from_text(
                f"{title}\n{body}"
            )
            yield self._policy(
                "LCD",
                f"L{lcd_id}",
                title,
                _date(_pick(row, ("rev_eff_date", "orig_det_eff_date"))),
                _date(_pick(row, ("rev_eff_date",))),
                body,
                "1",
                codes,
            )

    @staticmethod
    def _policy(
        ptype: str,
        pid: str,
        title: str,
        eff: str | None,
        mod: str | None,
        body: str,
        section: str,
        codes: list[str],
    ) -> PolicyRecord:
        return PolicyRecord(
            policy_id=pid,
            policy_type=ptype,
            title=title,
            effective_date=eff,
            last_modified=mod,
            mac=None,  # LCD MAC/state live in the contractor join tables (refinement)
            state=None,
            sections=[
                {
                    "heading": title or "Coverage",
                    "body": body,
                    "applicable_codes": codes,
                    "section_number": section,
                }
            ],
        )
